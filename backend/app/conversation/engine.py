import json

from pydantic import ValidationError

from app.schemas.assessment import (
    DefineOutput,
    IdentifyOutput,
    PlaybookCoverageStatus,
    utc_now,
)
from app.schemas.conversation import (
    AIConversationRecommendation,
    ConversationAction,
    ConversationContext,
    ConversationResult,
    ConversationRole,
    ConversationTurn,
    CrossCheckTarget,
    CrossCheckFinding,
    CrossCheckIssueType,
    QuestionEvidenceArea,
    StageConfig,
    StructuredEvidenceUpdate,
)
from app.services.ai_client import AIClient, AIClientError
from app.services.identify_foundation import claims_are_contradictory


class ConversationEngine:
    def __init__(self, config: StageConfig, ai_client: AIClient | None = None) -> None:
        self.config = config
        self.ai_client = ai_client

    def start_context(self) -> ConversationContext:
        return ConversationContext(stage=self.config.stage)

    def receive_turn(
        self, context: ConversationContext, turn: ConversationTurn
    ) -> ConversationResult:
        updated_context = context.model_copy(deep=True)
        updated_context.turns.append(turn)
        updated_context.evidence.extend(turn.evidence)
        updated_context.updated_at = utc_now()

        if turn.role == ConversationRole.user:
            answered_area = self._active_question_area(updated_context)
            answered_area = answered_area or self._matching_question_area(turn.content)
            answered_area = answered_area or self._next_uncovered_area(updated_context)
            self._update_context(updated_context, turn)
            findings = self._cross_check(updated_context, turn)
            updated_context.cross_check_findings.extend(findings)
            self._sync_gaps(updated_context, findings)
            retrieved = self._retrieve_evidence(turn)
            updated_context.retrieved_evidence.extend(retrieved)
            ai_recommendation = self._get_ai_recommendation(updated_context, turn)
            if self._has_vague_finding(findings):
                structured_updates = []
            else:
                structured_updates = self._apply_structured_updates(
                    updated_context, ai_recommendation
                )
                deterministic_update = self._structured_update_from_answer(
                    turn, answered_area
                )
                if deterministic_update is not None and not any(
                    update.field == deterministic_update.field
                    and update.value == deterministic_update.value
                    for update in structured_updates
                ):
                    structured_updates.append(deterministic_update)
        else:
            findings = []
            retrieved = []
            ai_recommendation = None
            structured_updates = []

        missing_fields = self._missing_fields(updated_context)
        output_valid, output_errors, structured_output = self._validate_output(
            updated_context
        )
        action = self._choose_action(
            updated_context=updated_context,
            latest_findings=findings,
            retrieved_evidence=retrieved,
            output_valid=output_valid,
            ai_recommendation=ai_recommendation,
        )
        revisit_target = self._latest_revisit_target(updated_context)
        revisit_target = revisit_target or self._validated_ai_revisit_target(
            ai_recommendation
        )
        next_question = self._next_question(
            updated_context, revisit_target, ai_recommendation
        )
        if next_question is not None:
            updated_context.turns.append(
                ConversationTurn(
                    role=ConversationRole.assistant,
                    content=next_question,
                )
            )

        return ConversationResult(
            context=updated_context,
            action=action,
            next_question=next_question,
            revisit_target=revisit_target,
            missing_fields=missing_fields,
            output_valid=output_valid,
            output_errors=output_errors,
            structured_output=structured_output,
            structured_evidence_updates=structured_updates,
        )

    def _update_context(
        self, context: ConversationContext, turn: ConversationTurn
    ) -> None:
        content = turn.content.strip()
        active_area = self._active_question_area(context)
        if active_area is not None:
            if self._is_sufficient_answer(content, active_area):
                context.collected_fields.setdefault(
                    active_area.structured_field, content
                )
                self._mark_area_covered(context, active_area.id)
            return

        area = self._matching_question_area(content)
        if area is not None:
            if self._is_sufficient_answer(content, area):
                context.collected_fields.setdefault(area.structured_field, content)
                self._mark_area_covered(context, area.id)
            return

        target = self._matching_target(content)
        if target is not None and target.fields:
            context.collected_fields.setdefault(target.fields[0], content)
            return

        for field in self.config.required_structured_fields:
            if field not in context.collected_fields:
                context.collected_fields[field] = content
                return

    def _cross_check(
        self, context: ConversationContext, turn: ConversationTurn
    ) -> list[CrossCheckFinding]:
        findings: list[CrossCheckFinding] = []
        content = turn.content.strip()
        active_area = self._active_question_area(context)
        target = self._matching_target(content)

        if (
            active_area is not None
            and not self._is_sufficient_answer(content, active_area)
        ) or len(content.split()) < 5:
            findings.append(
                CrossCheckFinding(
                    issue_type=CrossCheckIssueType.vagueness,
                    target=(
                        active_area.id
                        if active_area is not None
                        else target.name if target else "current_answer"
                    ),
                    message="The answer is too brief to support structured assessment.",
                )
            )

        if target is not None:
            previous_values = [
                previous.content
                for previous in context.turns[:-1]
                if previous.role == ConversationRole.user
                and self._matching_target(previous.content) == target
            ]
            if self._looks_contradictory(content, previous_values):
                findings.append(
                    CrossCheckFinding(
                        issue_type=CrossCheckIssueType.contradiction,
                        target=target.name,
                        message="The answer appears to conflict with earlier evidence.",
                    )
                )

        comparison_area_ids = (
            [active_area.id]
            if active_area is not None
            else self._target_area_ids(target)
        )
        for evidence in context.evidence:
            if comparison_area_ids and not (
                set(comparison_area_ids) & set(evidence.coverage_area_ids)
            ):
                continue
            if not claims_are_contradictory(content, evidence.claim):
                continue
            findings.append(
                CrossCheckFinding(
                    issue_type=CrossCheckIssueType.contradiction,
                    target=(
                        active_area.id
                        if active_area is not None
                        else target.name if target else "current_answer"
                    ),
                    message=(
                        "This answer conflicts with saved evidence from "
                        f"{evidence.source.title}."
                    ),
                    evidence_ids=[evidence.id],
                    source_activities=[
                        activity
                        for activity in [evidence.source_activity, "hot-seat"]
                        if activity is not None
                    ],
                )
            )
            break

        if not turn.evidence and self._mentions_evidence(content):
            findings.append(
                CrossCheckFinding(
                    issue_type=CrossCheckIssueType.gap,
                    target=target.name if target else "evidence",
                    message=(
                        "The answer references evidence but does not attach "
                        "a source."
                    ),
                )
            )

        return findings

    def _get_ai_recommendation(
        self, context: ConversationContext, turn: ConversationTurn
    ) -> AIConversationRecommendation | None:
        if self.ai_client is None:
            return None

        try:
            return self.ai_client.generate_structured(
                prompt=self._ai_prompt(context, turn),
                output_schema=AIConversationRecommendation,
                system=self.config.system_instructions,
            )
        except AIClientError:
            return None

    def _apply_structured_updates(
        self,
        context: ConversationContext,
        recommendation: AIConversationRecommendation | None,
    ) -> list[StructuredEvidenceUpdate]:
        if recommendation is None:
            return []

        accepted_updates: list[StructuredEvidenceUpdate] = []
        for update in recommendation.structured_updates:
            if not self._valid_structured_update(update):
                continue
            context.collected_fields.setdefault(update.field, update.value)
            area = self._area_for_field(update.field)
            if area is not None:
                self._mark_area_covered(context, area.id)
            accepted_updates.append(update)

        return accepted_updates

    def _sync_gaps(
        self, context: ConversationContext, findings: list[CrossCheckFinding]
    ) -> None:
        for finding in findings:
            if finding.issue_type in {
                CrossCheckIssueType.gap,
                CrossCheckIssueType.vagueness,
                CrossCheckIssueType.contradiction,
            }:
                if finding.message not in context.gaps:
                    context.gaps.append(finding.message)

    def _has_vague_finding(self, findings: list[CrossCheckFinding]) -> bool:
        return any(
            finding.issue_type == CrossCheckIssueType.vagueness
            for finding in findings
        )

    def _retrieve_evidence(self, turn: ConversationTurn) -> list[str]:
        if turn.evidence:
            return []
        if not self._mentions_evidence(turn.content):
            return []
        if "shared_rag_retrieval" not in self.config.available_tools:
            return []
        return ["shared_rag_retrieval:pending"]

    def _validate_output(
        self, context: ConversationContext
    ) -> tuple[bool, list[str], dict[str, object]]:
        structured_output = self._build_structured_output(context)
        if self.config.output_schema == "DefineOutput":
            try:
                DefineOutput.model_validate(structured_output)
            except ValidationError as exc:
                return False, [error["msg"] for error in exc.errors()], structured_output

            return True, [], structured_output

        if self.config.output_schema != "IdentifyOutput":
            return False, ["Unsupported output schema."], structured_output

        try:
            IdentifyOutput.model_validate(structured_output)
        except ValidationError as exc:
            return False, [error["msg"] for error in exc.errors()], structured_output

        return True, [], structured_output

    def _build_structured_output(
        self, context: ConversationContext
    ) -> dict[str, object]:
        if self.config.output_schema == "DefineOutput":
            return {
                "agreed_soi": None,
                "agreed_positioning": None,
                "agreed_values": [],
                "agreed_moments": [],
                "unresolved_questions": self._missing_fields(context),
                "evidence_references": [evidence.id for evidence in context.evidence],
                "source_handoff": "structured_outputs.identify.handoff",
            }
        return {
            "discovery_brief": context.collected_fields.get("discovery_brief"),
            "themes": [],
            "pestle_findings": [],
            "stakeholder_insights": [],
            "positioning_evidence": [],
            "social_contribution_evidence": [],
            "vulnerabilities_gaps": context.gaps,
            "open_questions": self._missing_fields(context),
            "evidence_references": [evidence.id for evidence in context.evidence],
        }

    def _choose_action(
        self,
        updated_context: ConversationContext,
        latest_findings: list[CrossCheckFinding],
        retrieved_evidence: list[str],
        output_valid: bool,
        ai_recommendation: AIConversationRecommendation | None,
    ) -> ConversationAction:
        if any(
            finding.issue_type
            in {CrossCheckIssueType.vagueness, CrossCheckIssueType.contradiction}
            for finding in latest_findings
        ):
            return ConversationAction.revisit_topic
        if retrieved_evidence:
            return ConversationAction.retrieve_evidence
        if not output_valid:
            return ConversationAction.validate_output
        if self._valid_ai_action(ai_recommendation, updated_context):
            return ai_recommendation.recommended_action
        if self._missing_fields(updated_context):
            return ConversationAction.ask_question
        return ConversationAction.continue_stage

    def _next_question(
        self,
        context: ConversationContext,
        revisit_target: str | None,
        ai_recommendation: AIConversationRecommendation | None,
    ) -> str | None:
        if revisit_target is not None:
            if ai_recommendation and ai_recommendation.next_question:
                if not self._was_question_asked(
                    context, ai_recommendation.next_question
                ):
                    return ai_recommendation.next_question
            area = self._area_for_id(revisit_target)
            if area is not None:
                return self._clarifying_question(area)
            return (
                f"Can you clarify the {revisit_target} point with more "
                "specific evidence?"
            )

        if (
            ai_recommendation
            and ai_recommendation.next_question
            and not self._was_question_asked(context, ai_recommendation.next_question)
        ):
            return ai_recommendation.next_question

        next_area = self._next_uncovered_area(context)
        if next_area is not None:
            return next_area.question

        return None

    def _latest_revisit_target(self, context: ConversationContext) -> str | None:
        if not context.cross_check_findings:
            return None
        for latest in reversed(context.cross_check_findings):
            if latest.issue_type not in {
                CrossCheckIssueType.vagueness,
                CrossCheckIssueType.contradiction,
            }:
                continue
            area = self._area_for_id(latest.target)
            if area is not None and area.id in context.covered_question_area_ids:
                continue
            return latest.target
        return None

    def _missing_fields(self, context: ConversationContext) -> list[str]:
        return [
            field
            for field in self.config.required_structured_fields
            if field not in context.collected_fields
        ]

    def _matching_target(self, content: str) -> CrossCheckTarget | None:
        lowered = content.lower()
        for target in self.config.cross_check_targets:
            if any(keyword in lowered for keyword in target.keywords):
                return target
        return None

    def _matching_question_area(self, content: str) -> QuestionEvidenceArea | None:
        lowered = content.lower()
        matches = [
            (sum(keyword in lowered for keyword in area.keywords), area)
            for area in self.config.question_evidence_areas
        ]
        score, area = max(matches, key=lambda item: item[0], default=(0, None))
        return area if score > 0 else None

    def _active_question_area(
        self, context: ConversationContext
    ) -> QuestionEvidenceArea | None:
        for finding in reversed(context.cross_check_findings):
            area = self._area_for_id(finding.target)
            if area is not None and area.id not in context.covered_question_area_ids:
                return area

        for turn in reversed(context.turns[:-1]):
            if turn.role != ConversationRole.assistant:
                continue
            for area in self.config.question_evidence_areas:
                if turn.content.strip().lower() == area.question.strip().lower():
                    return area
        return None

    def _is_sufficient_answer(
        self, content: str, area: QuestionEvidenceArea
    ) -> bool:
        words = [word.strip(".,!?;:()[]{}\"'").lower() for word in content.split()]
        words = [word for word in words if word]
        if len(words) < 8:
            return False

        generic_words = {
            "a",
            "an",
            "and",
            "do",
            "for",
            "better",
            "good",
            "great",
            "help",
            "make",
            "our",
            "their",
            "things",
            "stuff",
            "people",
            "them",
            "we",
            "something",
            "everything",
        }
        specific_words = [word for word in words if word not in generic_words]
        return len(specific_words) >= 5

    def _next_uncovered_area(
        self, context: ConversationContext
    ) -> QuestionEvidenceArea | None:
        asked_questions = {
            turn.content.strip().lower()
            for turn in context.turns
            if turn.role == ConversationRole.assistant
        }
        for target_status in ("uncovered", "partial"):
            for area in self.config.question_evidence_areas:
                status = context.question_area_statuses.get(area.id)
                if status is None:
                    status = (
                        "sufficient"
                        if area.id in context.covered_question_area_ids
                        else "uncovered"
                    )
                if status != target_status:
                    continue
                if area.question.strip().lower() in asked_questions:
                    continue
                return area
        return None

    def _mark_area_covered(self, context: ConversationContext, area_id: str) -> None:
        if area_id not in context.covered_question_area_ids:
            context.covered_question_area_ids.append(area_id)
        context.question_area_statuses[area_id] = PlaybookCoverageStatus.sufficient

    def _area_for_field(self, field: str) -> QuestionEvidenceArea | None:
        for area in self.config.question_evidence_areas:
            if area.structured_field == field:
                return area
        return None

    def _area_for_id(self, area_id: str) -> QuestionEvidenceArea | None:
        for area in self.config.question_evidence_areas:
            if area.id == area_id:
                return area
        return None

    def _clarifying_question(self, area: QuestionEvidenceArea) -> str:
        return (
            f"Can you make that more specific for {area.label.lower()}? "
            f"{area.evidence_prompt}"
        )

    def _valid_structured_update(self, update: StructuredEvidenceUpdate) -> bool:
        return update.field in self.config.required_structured_fields

    def _structured_update_from_answer(
        self,
        turn: ConversationTurn,
        area: QuestionEvidenceArea | None,
    ) -> StructuredEvidenceUpdate | None:
        """Keep useful answers as evidence even when the AI client is unavailable."""
        if area is None or not self._is_sufficient_answer(turn.content, area):
            return None
        return StructuredEvidenceUpdate(
            field=area.structured_field,
            value=turn.content.strip(),
            coverage_area_ids=[area.id],
        )

    def _target_area_ids(self, target: CrossCheckTarget | None) -> list[str]:
        if target is None:
            return []
        return [
            area.id
            for area in self.config.question_evidence_areas
            if area.structured_field in target.fields
        ]

    def _valid_ai_action(
        self,
        recommendation: AIConversationRecommendation | None,
        context: ConversationContext,
    ) -> bool:
        if recommendation is None:
            return False
        if recommendation.recommended_action == ConversationAction.continue_stage:
            return not self._missing_fields(context)
        if recommendation.recommended_action == ConversationAction.revisit_topic:
            return self._validated_ai_revisit_target(recommendation) is not None
        return recommendation.recommended_action in {
            ConversationAction.ask_question,
            ConversationAction.retrieve_evidence,
            ConversationAction.validate_output,
        }

    def _validated_ai_revisit_target(
        self, recommendation: AIConversationRecommendation | None
    ) -> str | None:
        if recommendation is None or recommendation.revisit_target is None:
            return None
        valid_targets = {target.name for target in self.config.cross_check_targets}
        if recommendation.revisit_target in valid_targets:
            return recommendation.revisit_target
        return None

    def _was_question_asked(
        self, context: ConversationContext, question: str
    ) -> bool:
        normalized_question = question.strip().lower()
        return any(
            turn.role == ConversationRole.assistant
            and turn.content.strip().lower() == normalized_question
            for turn in context.turns
        )

    def _ai_prompt(self, context: ConversationContext, turn: ConversationTurn) -> str:
        missing = ", ".join(self._missing_fields(context)) or "none"
        coverage = [
            {
                "areaId": area.id,
                "status": context.question_area_statuses.get(
                    area.id,
                    "sufficient"
                    if area.id in context.covered_question_area_ids
                    else "uncovered",
                ),
            }
            for area in self.config.question_evidence_areas
        ]
        areas = "\n".join(
            f"- {area.id}: {area.question} Evidence: {area.evidence_prompt}"
            for area in self.config.question_evidence_areas
        )
        recent_turns = "\n".join(
            f"{item.role.value}: {item.content}" for item in context.turns[-6:]
        )
        return (
            "Recommend the next Identify conversation move. Return only the "
            "structured schema requested by the caller.\n"
            f"Latest answer: {turn.content}\n"
            "Current evidence-area coverage (uncovered and partial remain eligible; "
            "do not re-ask sufficient areas):\n"
            f"{json.dumps(coverage, separators=(',', ':'))}\n"
            f"Missing structured fields: {missing}\n"
            f"Recent conversation:\n{recent_turns}\n"
            "Compact persisted evidence from this assessment only:\n"
            f"{json.dumps(context.identify_evidence_context, separators=(',', ':'))}\n"
            f"Question and evidence areas:\n{areas}\n"
            "Do not recommend stage transitions. Prefer genuinely missing or "
            "partial evidence, and avoid repeating evidence already sufficient "
            "elsewhere. Ask a natural clarification when saved evidence is weak "
            "or vague. Probe a tension only when the supplied evidence supports "
            "it. Never invent evidence, provenance, or a source claim. Prefer one "
            "targeted question or a focused revisit."
        )

    def _mentions_evidence(self, content: str) -> bool:
        lowered = content.lower()
        return any(
            marker in lowered
            for marker in ["evidence", "document", "report", "survey", "data"]
        )

    def _looks_contradictory(self, content: str, previous_values: list[str]) -> bool:
        if not previous_values:
            return False

        lowered = content.lower()
        has_negative_signal = any(
            signal in lowered
            for signal in [" no ", "not ", "never", "none", "opposite", "instead"]
        )
        if not has_negative_signal:
            return False

        return any(
            not any(
                signal in previous.lower() for signal in [" no ", "not ", "never"]
            )
            for previous in previous_values
        )
