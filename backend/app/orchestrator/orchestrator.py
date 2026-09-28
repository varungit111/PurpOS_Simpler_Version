from datetime import datetime
from typing import Any
from uuid import UUID

from app.conversation.engine import ConversationEngine
from app.schemas.assessment import (
    AssessmentLifecycleStatus,
    AssessmentSession,
    AssessmentSessionCreate,
    AssessmentStage,
    AssessmentStageStatus,
    AlignmentItemStatus,
    AlignmentStatus,
    DecisionCanvas,
    DefineOutput,
    DefineApprovalStatus,
    DefineProvenance,
    DefineState,
    DefineStatus,
    StressTestStatus,
    StressTestOutput,
    EvidenceStatus,
    EvidenceSource,
    IdentifyCompletionStatus,
    IdentifyEvidence,
    IdentifyOutput,
    utc_now,
)
from app.schemas.conversation import (
    ConversationAction,
    ConversationContext,
    ConversationRole,
    ConversationTurn,
    StageConfig,
)
from app.schemas.orchestrator import (
    ActivityConversationResult,
    ActivityProgress,
    AssessmentOrchestratorState,
    OrchestratorMessageResult,
    RevisitRoute,
    StageHandoff,
)
from app.services.ai_client import (
    AIClient,
    AIProviderError,
    MissingAIAPIKeyError,
    create_ai_client,
)
from app.services.define_generation import (
    build_define_output,
    generate_define_state,
    has_complete_positioning,
    has_usable_soi,
    repair_moments,
    repair_value_meanings,
    repair_positioning,
)
from app.services.define_evidence import (
    get_define_evidence_ids,
    get_define_evidence_records,
)
from app.services.define_questions import deduplicate_define_questions
from app.services.define_readiness import evaluate_define_readiness
from app.services.stress_test import (
    build_stress_test_output,
    evaluate_stress_test,
    recover_legacy_stress_test,
)
from app.services.alignment import (
    adopt_move,
    evaluate_decision,
    initialize_alignment,
    reframe_decision,
)
from app.services.identify_completion import build_identify_handoff
from app.services.identify_completion import get_persisted_identify_handoff
from app.services.identify_readiness import evaluate_identify_readiness
from app.services.identify_foundation import coverage_area_ids_for_text
from app.services.identify_evidence_context import build_identify_evidence_context
from app.stages.registry import get_next_stage, get_stage_config
from app.store.sessions import session_store


class OrchestratorError(Exception):
    pass


class SessionNotFoundError(OrchestratorError):
    pass


class StageConfigNotFoundError(OrchestratorError):
    pass


class InvalidStageTransitionError(OrchestratorError):
    pass


class IdentifyCompletionBlockedError(OrchestratorError):
    def __init__(self, readiness) -> None:
        super().__init__("Identify is not ready to complete.")
        self.readiness = readiness


class DefineEntryBlockedError(OrchestratorError):
    pass


class DefineItemNotFoundError(OrchestratorError):
    pass


class DefineCompletionBlockedError(OrchestratorError):
    def __init__(self, readiness) -> None:
        super().__init__("Define is not ready to complete.")
        self.readiness = readiness


class StressTestBlockedError(OrchestratorError):
    pass


class StressTestCriterionNotFoundError(OrchestratorError):
    pass


class AlignmentBlockedError(OrchestratorError):
    pass


class AlignmentItemNotFoundError(OrchestratorError):
    pass


class PurpOSOrchestrator:
    def __init__(self, ai_client: AIClient | None = None) -> None:
        self._ai_client = ai_client
        self._states: dict[UUID, AssessmentOrchestratorState] = {}

    def start_assessment(
        self,
        stage: AssessmentStage = AssessmentStage.identify,
        payload: AssessmentSessionCreate | None = None,
    ) -> AssessmentOrchestratorState:
        if payload is not None:
            stage = payload.stage
        if stage != AssessmentStage.identify:
            raise InvalidStageTransitionError(
                "Assessments must start in Identify."
            )
        config = self._require_stage_config(stage)
        session = session_store.create(payload or AssessmentSessionCreate(stage=stage))
        engine = ConversationEngine(config, ai_client=self._ai_client)
        state = AssessmentOrchestratorState(
            session_id=session.id,
            current_stage=stage,
            stage_config=config,
            context=engine.start_context(),
        )
        self._states[session.id] = state
        self._persist_state(state)
        return state.model_copy(deep=True)

    def get_state(self, session_id: UUID) -> AssessmentOrchestratorState:
        return self._require_state(session_id).model_copy(deep=True)

    def handle_message(
        self, session_id: UUID, content: str, ai_client: AIClient | None = None
    ) -> OrchestratorMessageResult:
        state = self._require_state(session_id)
        engine = ConversationEngine(
            state.stage_config, ai_client=ai_client or self._ai_client
        )
        turn = ConversationTurn(role=ConversationRole.user, content=content)
        result = engine.receive_turn(state.context, turn)

        state.context = result.context
        state.structured_outputs[state.current_stage] = result.structured_output
        if result.action == ConversationAction.revisit_topic and result.revisit_target:
            state.revisit_routes.append(
                RevisitRoute(
                    stage=state.current_stage,
                    topic=result.revisit_target,
                    reason="Conversation engine requested a targeted revisit.",
                )
            )
        state.updated_at = result.context.updated_at
        self._persist_state(state)

        return OrchestratorMessageResult(
            state=state.model_copy(deep=True), conversation_result=result
        )

    def handle_activity_message(
        self,
        session_id: UUID,
        activity_id: str,
        content: str,
        ai_client: AIClient | None = None,
    ) -> ActivityConversationResult:
        result = self.handle_message(
            session_id=session_id,
            content=content,
            ai_client=ai_client,
        )
        evidence_updates = self._persist_activity_evidence(
            session_id=session_id,
            activity_id=activity_id,
            result=result,
        )
        return ActivityConversationResult(
            state=result.state,
            conversation_result=result.conversation_result,
            activity_id=activity_id,
            activity_status=self._activity_status(result),
            progress=self._activity_progress(result.state),
            evidence_updates=evidence_updates,
        )

    def complete_stage(self, session_id: UUID) -> AssessmentOrchestratorState:
        state = self._require_state(session_id)
        if state.current_stage == AssessmentStage.identify:
            return self.complete_identify(session_id)

        # Later stages can retain the generic completion mechanism until their
        # own methodology-specific readiness rules are implemented.
        state.structured_outputs[state.current_stage] = (
            ConversationEngine(state.stage_config, ai_client=self._ai_client)
            .receive_turn(
                state.context,
                ConversationTurn(
                    role=ConversationRole.system,
                    content="Validate current structured output.",
                ),
            )
            .structured_output
        )
        state.lifecycle_status = AssessmentLifecycleStatus.stage_completed
        state.handoffs.append(
            StageHandoff(
                from_stage=state.current_stage,
                to_stage=get_next_stage(state.current_stage),
                note="Stage marked complete without applying a completion threshold.",
            )
        )
        self._persist_state(state)
        return state.model_copy(deep=True)

    def complete_identify(self, session_id: UUID) -> AssessmentOrchestratorState:
        """Validate, snapshot, and persist the Identify-to-Define checkpoint."""
        state = self._require_state(session_id)
        if state.current_stage != AssessmentStage.identify:
            raise InvalidStageTransitionError("Only Identify can use this checkpoint.")
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")

        readiness = evaluate_identify_readiness(session)
        if not readiness.can_complete:
            raise IdentifyCompletionBlockedError(readiness)
        if session.identify.completion_status == IdentifyCompletionStatus.completed:
            return state.model_copy(deep=True)

        completed_at = utc_now()
        handoff = build_identify_handoff(session, readiness, completed_at)
        existing_output = state.structured_outputs.get(AssessmentStage.identify, {})
        state.structured_outputs[AssessmentStage.identify] = {
            **existing_output,
            "handoff": handoff.model_dump(mode="json", by_alias=True),
        }
        state.lifecycle_status = AssessmentLifecycleStatus.stage_completed
        state.next_stage = AssessmentStage.define
        state.handoffs.append(
            StageHandoff(
                from_stage=AssessmentStage.identify,
                to_stage=AssessmentStage.define,
                note="Identify completed; Define is ready but not yet started.",
                output_reference="structured_outputs.identify.handoff",
            )
        )
        self._persist_state(
            state,
            identify_completion_status=IdentifyCompletionStatus.completed,
            identify_completed_at=completed_at,
        )
        return state.model_copy(deep=True)

    def initialize_define(
        self,
        session_id: UUID,
        ai_client: AIClient | None = None,
    ) -> DefineState:
        """Start Define from the persisted Identify handoff."""
        state = self._require_state(session_id)
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")
        handoff = self._validated_define_handoff(session)
        if session.define.status != DefineStatus.not_started:
            needs_soi_repair = (
                session.define.soi_candidate is None
                or (
                    session.define.soi_candidate.approval_status
                    == DefineApprovalStatus.ai_proposed
                    and not has_usable_soi(session.define)
                )
            )
            needs_soi_reference_repair = (
                session.define.soi_candidate is not None
                and session.define.soi_candidate.approval_status
                == DefineApprovalStatus.ai_proposed
                and not set(session.define.soi_candidate.evidence_ids).issubset(
                    set(session.define.evidence_references)
                )
            )
            needs_positioning_repair = (
                session.define.positioning.approval_status
                == DefineApprovalStatus.ai_proposed
                and not has_complete_positioning(session.define)
            )
            needs_values_repair = any(
                value.approval_status == DefineApprovalStatus.ai_proposed
                and not (value.meaning or "").strip()
                for value in session.define.values
            )
            needs_moments_repair = any(
                moment.approval_status == DefineApprovalStatus.ai_proposed
                and (
                    any(
                        not (value or "").strip()
                        for value in (
                            moment.question,
                            moment.today,
                            moment.desired_state,
                            moment.the_move,
                        )
                    )
                    or not any(item.strip() for item in moment.supporting_evidence)
                )
                for moment in session.define.moments
            )
            deduplicated_questions = deduplicate_define_questions(
                session.define.unresolved_questions
            )
            needs_question_repair = (
                deduplicated_questions != session.define.unresolved_questions
            )
            if session.define.status == DefineStatus.in_progress and (
                needs_soi_repair
                or needs_soi_reference_repair
                or needs_positioning_repair
                or needs_values_repair
                or needs_moments_repair
                or needs_question_repair
            ):
                repaired = session.define.model_copy(deep=True)
                generated = (
                    generate_define_state(
                        handoff,
                        ai_client=ai_client or self._ai_client,
                    )
                    if needs_soi_repair or needs_positioning_repair
                    else None
                )
                if (
                    needs_soi_repair
                    and generated is not None
                    and has_usable_soi(generated)
                ):
                    repaired.soi_candidate = generated.soi_candidate
                if repaired.soi_candidate is not None:
                    repaired.evidence_references = sorted(
                        {
                            *repaired.evidence_references,
                            *repaired.soi_candidate.evidence_ids,
                        },
                        key=str,
                    )
                if (
                    needs_positioning_repair
                    and generated is not None
                    and has_complete_positioning(generated)
                ):
                    repaired.positioning = repair_positioning(
                        repaired.positioning,
                        generated.positioning,
                        organisation=handoff.brief.organisation_name,
                    )
                if needs_values_repair or needs_moments_repair:
                    fallback = generate_define_state(handoff)
                if needs_values_repair:
                    repaired.values = repair_value_meanings(
                        repaired.values,
                        fallback.values,
                        handoff=handoff,
                    )
                if needs_moments_repair:
                    repaired.moments = repair_moments(
                        repaired.moments,
                        fallback.moments,
                        handoff=handoff,
                    )
                if needs_question_repair:
                    repaired.unresolved_questions = deduplicated_questions
                    repaired.output = build_define_output(repaired)
                if repaired != session.define:
                    return self._save_define_state(session_id, repaired)
            return session.define.model_copy(deep=True)

        config = self._require_stage_config(AssessmentStage.define)
        engine = ConversationEngine(config, ai_client=ai_client or self._ai_client)
        define_state = generate_define_state(
            handoff,
            ai_client=ai_client or self._ai_client,
        )

        state.current_stage = AssessmentStage.define
        state.next_stage = AssessmentStage.stress_test
        state.stage_config = config
        state.context = engine.start_context()
        state.lifecycle_status = AssessmentLifecycleStatus.active
        state.structured_outputs[AssessmentStage.define] = (
            define_state.output.model_dump(mode="json", by_alias=True)
            if define_state.output is not None
            else {}
        )
        saved = session_store.update_define_state(
            session_id,
            define_state,
            stage=AssessmentStage.define,
            lifecycle_status=AssessmentLifecycleStatus.active,
            next_stage=AssessmentStage.stress_test,
        )
        if saved is None:
            raise SessionNotFoundError("Assessment session not found.")
        self._states[session_id] = state
        self._persist_state(state)
        return saved

    def update_define_positioning(
        self,
        session_id: UUID,
        updates: dict[str, object],
        *,
        approval_status: DefineApprovalStatus = DefineApprovalStatus.user_edited,
    ) -> DefineState:
        state = self._editable_define_state(session_id)
        self._validate_define_evidence_ids(session_id, updates.get("evidence_ids"))
        state.positioning = state.positioning.model_copy(
            update={
                **updates,
                "approval_status": approval_status,
                "provenance": _user_updated_provenance(state.source_handoff),
            },
            deep=True,
        )
        return self._save_define_state(session_id, state)

    def update_define_soi(self, session_id: UUID, updates: dict[str, object], *, approval_status=DefineApprovalStatus.user_edited) -> DefineState:
        state = self._editable_define_state(session_id)
        if state.soi_candidate is None:
            raise DefineItemNotFoundError("Define SOI candidate not found.")
        state.soi_candidate = state.soi_candidate.model_copy(update={**updates, "approval_status": approval_status, "provenance": _user_updated_provenance(state.source_handoff)}, deep=True)
        return self._save_define_state(session_id, state)

    def complete_define(self, session_id: UUID):
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")
        if session.stage != AssessmentStage.define:
            raise DefineEntryBlockedError("Define is not the current active stage.")
        readiness = evaluate_define_readiness(session)
        if not readiness.can_complete:
            raise DefineCompletionBlockedError(readiness)
        if session.define.status != DefineStatus.completed:
            session.define.status = DefineStatus.completed
            session.define.updated_at = utc_now()
            session.define.output = build_define_output(session.define)
            session.stress_test = evaluate_stress_test(
                session_id,
                session.define.output,
                evidence_records=get_define_evidence_records(session),
                ai_client=self._ai_client,
            )
            session.stage = AssessmentStage.stress_test
            session.next_stage = AssessmentStage.align
            session.lifecycle_status = AssessmentLifecycleStatus.active
            session.stage_statuses[AssessmentStage.define] = AssessmentStageStatus.completed
            session.stage_statuses[AssessmentStage.stress_test] = AssessmentStageStatus.in_progress
            session.stage_statuses.setdefault(AssessmentStage.align, AssessmentStageStatus.not_started)
            session.structured_outputs[AssessmentStage.define] = session.define.output.model_dump(mode="json", by_alias=True)
            session.structured_outputs[AssessmentStage.stress_test] = build_stress_test_output(session.stress_test).model_dump(mode="json", by_alias=True)
            session.handoffs.append(StageHandoff(from_stage=AssessmentStage.define, to_stage=AssessmentStage.stress_test, note="Agreed Define output passed to the fixed eight-point SOI Stress Test.", output_reference="structured_outputs.define" ).model_dump(mode="json"))
            session_store.save(session)
            self._states.pop(session_id, None)
        return readiness, session.define.output

    def evaluate_stress_test(self, session_id: UUID):
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")
        if session.define.status != DefineStatus.completed or session.define.output is None:
            raise StressTestBlockedError("Define must be completed before Stress Test.")
        if not session.stress_test.criteria:
            session.stress_test = evaluate_stress_test(
                session_id,
                session.define.output,
                evidence_records=get_define_evidence_records(session),
                ai_client=self._ai_client,
            )
            session_store.update_stress_test_state(session_id, session.stress_test)
        else:
            recovered = recover_legacy_stress_test(
                session.stress_test,
                session.define.output,
                evidence_records=get_define_evidence_records(session),
                ai_client=self._ai_client,
            )
            if recovered != session.stress_test:
                saved = session_store.update_stress_test_state(session_id, recovered)
                if saved is None:
                    raise SessionNotFoundError("Assessment session not found.")
                return saved
        return session.stress_test.model_copy(deep=True)

    def update_stress_test_criterion(self, session_id: UUID, criterion_id: str, updates: dict[str, object], *, approval_status=DefineApprovalStatus.user_edited):
        state = self.evaluate_stress_test(session_id)
        for index, criterion in enumerate(state.criteria):
            if criterion.criterion_id == criterion_id:
                evidence_ids = updates.get("supporting_evidence_ids")
                if evidence_ids is not None and not set(evidence_ids).issubset(set(state.evidence_references)):
                    raise StressTestBlockedError("Criterion evidence must belong to the Define handoff.")
                state.criteria[index] = criterion.model_copy(update={**updates, "approval_status": approval_status, "provenance": _user_updated_provenance("structured_outputs.define.handoff")}, deep=True)
                saved = session_store.update_stress_test_state(session_id, state)
                if saved is None: raise SessionNotFoundError("Assessment session not found.")
                return saved
        raise StressTestCriterionNotFoundError("Stress Test criterion not found.")

    def update_stress_test_review(self, session_id: UUID, response: str):
        state = self.evaluate_stress_test(session_id)
        state.overarching_response = response
        saved = session_store.update_stress_test_state(session_id, state)
        if saved is None: raise SessionNotFoundError("Assessment session not found.")
        return saved

    def complete_stress_test(self, session_id: UUID):
        state = self.evaluate_stress_test(session_id)
        if len(state.criteria) != 8:
            raise StressTestBlockedError("All eight CORE Playbook criteria are required.")
        if any(item.approval_status != DefineApprovalStatus.agreed for item in state.criteria):
            raise StressTestBlockedError("Review and agree all eight criteria before completing the gate.")
        if any(item.status == "insufficient-evidence" for item in state.criteria):
            raise StressTestBlockedError("Resolve criteria with insufficient evidence before completing the gate.")
        if not state.overarching_response:
            raise StressTestBlockedError("Answer the overarching Playbook question before completing the gate.")
        state.status = StressTestStatus.completed
        state.output = build_stress_test_output(state)
        saved = session_store.update_stress_test_state(session_id, state, lifecycle_status=AssessmentLifecycleStatus.stage_completed)
        if saved is None: raise SessionNotFoundError("Assessment session not found.")
        self._states.pop(session_id, None)
        return saved

    def initialize_alignment(self, session_id: UUID):
        session = self._alignment_ready_session(session_id)
        if session.alignment.status == AlignmentStatus.in_progress:
            return session.alignment.model_copy(deep=True)
        assert session.define.output is not None
        assert session.stress_test.output is not None
        state = initialize_alignment(
            session_id,
            session.define.output,
            session.stress_test.output,
            self._ai_client,
        )
        saved = session_store.update_alignment_state(session_id, state)
        if saved is None:
            raise SessionNotFoundError("Assessment session not found.")
        session = session_store.get(session_id)
        assert session is not None
        session.handoffs.append(
            StageHandoff(
                from_stage=AssessmentStage.stress_test,
                to_stage=AssessmentStage.align,
                note="Completed Define and Stress Test outputs passed to Alignment.",
                output_reference="structured_outputs.align",
            ).model_dump(mode="json")
        )
        session_store.save(session)
        self._states.pop(session_id, None)
        return saved

    def create_alignment_decision(self, session_id: UUID, question: str):
        state, _, _ = self._active_alignment(session_id)
        decision = DecisionCanvas(
            originalQuestion=question,
            evidenceReferences=state.evidence_references,
            provenance=DefineProvenance(
                status=EvidenceStatus.user_confirmed,
                rationale="Decision question entered by the user.",
                updatedAt=utc_now(),
                sourceHandoff="structured_outputs.align",
            ),
        )
        state.decisions.append(decision)
        self._save_alignment(session_id, state)
        return decision

    def reframe_alignment_decision(self, session_id: UUID, decision_id: UUID):
        state, define_output, stress_output = self._active_alignment(session_id)
        index = self._decision_index(state, decision_id)
        state.decisions[index] = reframe_decision(
            state.decisions[index], define_output, stress_output, self._ai_client
        )
        return self._save_alignment(session_id, state).decisions[index]

    def evaluate_alignment_decision(self, session_id: UUID, decision_id: UUID):
        state, define_output, stress_output = self._active_alignment(session_id)
        index = self._decision_index(state, decision_id)
        state.decisions[index] = evaluate_decision(
            state.decisions[index], define_output, stress_output
        )
        return self._save_alignment(session_id, state).decisions[index]

    def update_alignment_move(self, session_id: UUID, move_id: UUID, adopted: bool):
        state, _, _ = self._active_alignment(session_id)
        for decision_index, decision in enumerate(state.decisions):
            for move_index, move in enumerate(decision.suggested_moves):
                if move.id != move_id:
                    continue
                if adopted:
                    if move.adopted:
                        return move.model_copy(deep=True)
                    updated, action = adopt_move(move)
                    decision.suggested_moves[move_index] = updated
                    if action.id not in decision.adopted_action_ids:
                        decision.adopted_action_ids.append(action.id)
                        state.adopted_actions.append(action)
                else:
                    decision.suggested_moves[move_index] = move.model_copy(
                        update={"adopted": False, "status": AlignmentItemStatus.proposed}
                    )
                    removed = [item.id for item in state.adopted_actions if item.source_move_id == move_id]
                    state.adopted_actions = [item for item in state.adopted_actions if item.source_move_id != move_id]
                    decision.adopted_action_ids = [item for item in decision.adopted_action_ids if item not in removed]
                decision.updated_at = utc_now()
                state.decisions[decision_index] = decision
                return self._save_alignment(session_id, state).decisions[decision_index].suggested_moves[move_index]
        raise AlignmentItemNotFoundError("Alignment suggested move not found.")

    def _alignment_ready_session(self, session_id: UUID) -> AssessmentSession:
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")
        if session.define.status != DefineStatus.completed or session.define.output is None:
            raise AlignmentBlockedError("A completed DefineOutput is required before Alignment.")
        if session.stress_test.status != StressTestStatus.completed or session.stress_test.output is None:
            raise AlignmentBlockedError("A completed StressTestOutput is required before Alignment.")
        if session.next_stage != AssessmentStage.align and session.stage != AssessmentStage.align:
            raise AlignmentBlockedError("The lifecycle is not ready for Alignment.")
        return session

    def _active_alignment(self, session_id: UUID):
        session = self._alignment_ready_session(session_id)
        if session.stage != AssessmentStage.align or session.alignment.status != AlignmentStatus.in_progress:
            raise AlignmentBlockedError("Alignment has not been initialized.")
        assert isinstance(session.define.output, DefineOutput)
        assert isinstance(session.stress_test.output, StressTestOutput)
        return session.alignment.model_copy(deep=True), session.define.output, session.stress_test.output

    def _save_alignment(self, session_id: UUID, state):
        saved = session_store.update_alignment_state(session_id, state)
        if saved is None:
            raise SessionNotFoundError("Assessment session not found.")
        return saved

    @staticmethod
    def _decision_index(state, decision_id: UUID) -> int:
        for index, decision in enumerate(state.decisions):
            if decision.id == decision_id:
                return index
        raise AlignmentItemNotFoundError("Alignment decision not found.")

    def update_define_value(
        self,
        session_id: UUID,
        value_id: UUID,
        updates: dict[str, object],
        *,
        approval_status: DefineApprovalStatus = DefineApprovalStatus.user_edited,
    ) -> DefineState:
        state = self._editable_define_state(session_id)
        self._validate_define_evidence_ids(session_id, updates.get("evidence_ids"))
        for index, value in enumerate(state.values):
            if value.id == value_id:
                state.values[index] = value.model_copy(
                    update={
                        **updates,
                        "approval_status": approval_status,
                        "provenance": _user_updated_provenance(state.source_handoff),
                    },
                    deep=True,
                )
                return self._save_define_state(session_id, state)
        raise DefineItemNotFoundError("Define value not found.")

    def update_define_moment(
        self,
        session_id: UUID,
        moment_id: UUID,
        updates: dict[str, object],
        *,
        approval_status: DefineApprovalStatus = DefineApprovalStatus.user_edited,
    ) -> DefineState:
        state = self._editable_define_state(session_id)
        self._validate_define_evidence_ids(session_id, updates.get("evidence_ids"))
        for index, moment in enumerate(state.moments):
            if moment.id == moment_id:
                state.moments[index] = moment.model_copy(
                    update={
                        **updates,
                        "approval_status": approval_status,
                        "provenance": _user_updated_provenance(state.source_handoff),
                    },
                    deep=True,
                )
                return self._save_define_state(session_id, state)
        raise DefineItemNotFoundError("Define moment not found.")

    def revisit_topic(
        self, session_id: UUID, topic: str, reason: str
    ) -> AssessmentOrchestratorState:
        state = self._require_state(session_id)
        state.revisit_routes.append(
            RevisitRoute(stage=state.current_stage, topic=topic, reason=reason)
        )
        self._persist_state(state)
        return state.model_copy(deep=True)

    def advance_stage(
        self, session_id: UUID, next_stage: AssessmentStage | None = None
    ) -> AssessmentOrchestratorState:
        state = self._require_state(session_id)
        target_stage = next_stage or get_next_stage(state.current_stage)
        if target_stage is None:
            raise InvalidStageTransitionError("No later stage is available.")

        expected_stage = get_next_stage(state.current_stage)
        if target_stage != expected_stage:
            raise InvalidStageTransitionError(
                "Stage transitions must follow SOI order."
            )
        if target_stage == AssessmentStage.define:
            session = session_store.get(session_id)
            if session is None:
                raise SessionNotFoundError("Assessment session not found.")
            self._validated_define_handoff(session)

        config = self._require_stage_config(target_stage)
        engine = ConversationEngine(config, ai_client=self._ai_client)
        state.current_stage = target_stage
        state.stage_config = config
        state.context = engine.start_context()
        state.lifecycle_status = AssessmentLifecycleStatus.active
        self._persist_state(state)
        return state.model_copy(deep=True)

    def _validated_define_handoff(self, session: AssessmentSession):
        if session.identify.completion_status != IdentifyCompletionStatus.completed:
            raise DefineEntryBlockedError("Identify must be completed before Define.")
        if session.stage_statuses.get(AssessmentStage.identify) != (
            AssessmentStageStatus.completed
        ):
            raise DefineEntryBlockedError("Identify lifecycle status is not completed.")
        if session.next_stage not in {AssessmentStage.define, AssessmentStage.stress_test}:
            raise DefineEntryBlockedError("Lifecycle does not allow Define entry.")
        handoff = get_persisted_identify_handoff(session)
        if handoff is None:
            raise DefineEntryBlockedError("Identify handoff is missing.")
        return handoff

    def _editable_define_state(self, session_id: UUID) -> DefineState:
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")
        self._validated_define_handoff(session)
        if session.define.status == DefineStatus.not_started:
            raise DefineEntryBlockedError("Define has not been initialized.")
        if session.stage != AssessmentStage.define:
            raise DefineEntryBlockedError("Define is not the current active stage.")
        return session.define.model_copy(deep=True)

    def _save_define_state(
        self,
        session_id: UUID,
        define_state: DefineState,
    ) -> DefineState:
        saved = session_store.update_define_state(
            session_id,
            define_state,
            stage=AssessmentStage.define,
            lifecycle_status=AssessmentLifecycleStatus.active,
            next_stage=AssessmentStage.stress_test,
        )
        if saved is None:
            raise SessionNotFoundError("Assessment session not found.")
        state = self._require_state(session_id)
        if saved.output is not None:
            state.structured_outputs[AssessmentStage.define] = saved.output.model_dump(
                mode="json",
                by_alias=True,
            )
        state.lifecycle_status = AssessmentLifecycleStatus.active
        state.current_stage = AssessmentStage.define
        state.next_stage = AssessmentStage.stress_test
        self._states[session_id] = state
        return saved

    def _validate_define_evidence_ids(
        self,
        session_id: UUID,
        evidence_ids: object,
    ) -> None:
        if evidence_ids is None:
            return
        if not isinstance(evidence_ids, list):
            raise DefineEntryBlockedError("Evidence IDs must be a list.")
        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")
        handoff = get_persisted_identify_handoff(session)
        if handoff is None:
            raise DefineEntryBlockedError("Identify handoff is missing.")
        allowed = get_define_evidence_ids(session)
        requested = set(evidence_ids)
        if not requested.issubset(allowed):
            raise DefineEntryBlockedError(
                "One or more evidence IDs are not part of the Identify handoff."
            )

    def get_structured_outputs(self, session_id: UUID) -> dict[str, dict[str, Any]]:
        state = self._require_state(session_id)
        return {
            stage.value: output.copy()
            for stage, output in state.structured_outputs.items()
        }

    def clear(self) -> None:
        self._states.clear()

    def _require_state(self, session_id: UUID) -> AssessmentOrchestratorState:
        state = self._states.get(session_id)
        if state is not None:
            session = session_store.get(session_id)
            if session is not None and session.stage == state.current_stage:
                state.context = self._hydrate_identify_context(
                    state.context, session
                )
            return state

        session = session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError("Assessment session not found.")

        config = self._require_stage_config(session.stage)
        engine = ConversationEngine(config, ai_client=self._ai_client)
        saved_context = session.stage_states.get(session.stage)
        context = (
            ConversationContext.model_validate(saved_context)
            if saved_context is not None
            else self._context_from_session(session, engine)
        )
        state = AssessmentOrchestratorState(
            session_id=session.id,
            lifecycle_status=session.lifecycle_status,
            current_stage=session.stage,
            next_stage=session.next_stage,
            stage_config=config,
            context=self._hydrate_identify_context(context, session),
            handoffs=[StageHandoff.model_validate(item) for item in session.handoffs],
            revisit_routes=[
                RevisitRoute.model_validate(item) for item in session.revisit_routes
            ],
            structured_outputs=session.structured_outputs,
            updated_at=session.updated_at,
        )
        self._states[session.id] = state
        return state

    def _require_stage_config(self, stage: AssessmentStage) -> StageConfig:
        config = get_stage_config(stage)
        if config is None:
            raise StageConfigNotFoundError(
                f"No StageConfig is registered for {stage.value}."
            )
        return config

    def _context_from_session(
        self, session: AssessmentSession, engine: ConversationEngine
    ) -> ConversationContext:
        context = engine.start_context()
        return self._hydrate_identify_context(context, session)

    def _hydrate_identify_context(
        self, context: ConversationContext, session: AssessmentSession
    ) -> ConversationContext:
        context.evidence = session.identify.evidence
        context.identify_evidence_context = build_identify_evidence_context(
            session.identify,
            source_activities={
                "ai-detective",
                "signal-hunt",
                "who-matters",
                "hot-seat",
                "company-cards",
                "day-in-their-shoes",
                "where-do-you-stand",
                "perception-gaps",
            },
            preferred_area_ids={
                coverage.area_id
                for coverage in session.identify.playbook_coverage
                if coverage.status != "sufficient"
            },
        )
        for coverage in session.identify.playbook_coverage:
            context.question_area_statuses[coverage.area_id] = coverage.status
            if coverage.status != "uncovered" and (
                coverage.area_id not in context.covered_question_area_ids
            ):
                context.covered_question_area_ids.append(coverage.area_id)
        if session.identify.output.stakeholder_insights:
            context.collected_fields["stakeholder_insights"] = (
                "Stakeholder map captured through Who Matters."
            )
            for question_area_id in (
                "customer_needs",
                "employee_experience",
                "partner_supplier_context",
            ):
                if question_area_id not in context.covered_question_area_ids:
                    context.covered_question_area_ids.append(question_area_id)
        return context

    def _persist_state(
        self,
        state: AssessmentOrchestratorState,
        identify_completion_status: IdentifyCompletionStatus | None = None,
        identify_completed_at: datetime | None = None,
    ) -> None:
        # Raw conversation turns remain temporary; resumable structured context is saved.
        state.updated_at = utc_now()
        resumable_context = state.context.model_copy(update={"turns": []})
        session_store.save_lifecycle_state(
            state.session_id,
            stage=state.current_stage,
            lifecycle_status=state.lifecycle_status,
            stage_state=resumable_context.model_dump(mode="json"),
            structured_outputs={
                stage: output.copy()
                for stage, output in state.structured_outputs.items()
            },
            handoffs=[item.model_dump(mode="json") for item in state.handoffs],
            revisit_routes=[
                item.model_dump(mode="json") for item in state.revisit_routes
            ],
            next_stage=state.next_stage,
            identify_completion_status=identify_completion_status,
            identify_completed_at=identify_completed_at,
        )

    def _persist_activity_evidence(
        self,
        session_id: UUID,
        activity_id: str,
        result: OrchestratorMessageResult,
    ) -> list[IdentifyEvidence]:
        if result.state.current_stage != AssessmentStage.identify:
            return []
        if activity_id != "hot-seat":
            return []

        evidence_updates = [
            IdentifyEvidence(
                source=EvidenceSource(title="Hot Seat", source_type="hot_seat"),
                claim=update.value,
                summary=update.field,
                confidence=update.confidence,
                sourceActivity=activity_id,
                coverageAreaIds=(
                    update.coverage_area_ids
                    or coverage_area_ids_for_text(f"{update.field} {update.value}")
                ),
                evidenceStatus=EvidenceStatus.user_confirmed,
                sourceReference=_latest_user_turn_reference(result),
            )
            for update in result.conversation_result.structured_evidence_updates
        ]
        hot_seat_output = IdentifyOutput.model_validate(
            result.conversation_result.structured_output
        )
        existing_state = session_store.get_identify_state(session_id)
        existing_evidence = [] if existing_state is None else existing_state.evidence
        existing_claims = {
            (item.source_activity, item.claim.strip().lower())
            for item in existing_evidence
        }
        evidence_updates = [
            item
            for item in evidence_updates
            if (item.source_activity, item.claim.strip().lower()) not in existing_claims
        ]
        all_evidence = [*existing_evidence, *evidence_updates]
        identify_output = (
            IdentifyOutput()
            if existing_state is None
            else existing_state.output.model_copy(deep=True)
        )
        if hot_seat_output.discovery_brief is not None:
            identify_output.discovery_brief = hot_seat_output.discovery_brief
        identify_output.vulnerabilities_gaps = hot_seat_output.vulnerabilities_gaps
        identify_output.open_questions = hot_seat_output.open_questions
        identify_output.evidence_references = [
            evidence.id for evidence in all_evidence
        ]
        session_store.update_identify_state(
            session_id=session_id,
            output=identify_output,
            evidence=all_evidence,
        )
        return evidence_updates

    def _activity_status(self, result: OrchestratorMessageResult) -> str:
        action = result.conversation_result.action
        if action == ConversationAction.revisit_topic:
            return "needs-you"
        if action == ConversationAction.retrieve_evidence:
            return "ai-running"
        return "in-progress"

    def _activity_progress(
        self, state: AssessmentOrchestratorState
    ) -> ActivityProgress:
        total = max(len(state.stage_config.question_evidence_areas), 1)
        current = min(len(state.context.covered_question_area_ids), total)
        return ActivityProgress(
            current=current,
            total=total,
            label="Identify evidence areas",
        )


def _configured_ai_client() -> AIClient | None:
    try:
        return create_ai_client()
    except (MissingAIAPIKeyError, AIProviderError):
        return None


orchestrator = PurpOSOrchestrator(ai_client=_configured_ai_client())


def _latest_user_turn_reference(result: OrchestratorMessageResult) -> str | None:
    for turn in reversed(result.conversation_result.context.turns):
        if turn.role == ConversationRole.user:
            return f"conversation-turn:{turn.id}"
    return None


def _user_updated_provenance(source_handoff: str | None) -> DefineProvenance:
    return DefineProvenance(
        status=EvidenceStatus.user_confirmed,
        rationale="Updated by the user during Define.",
        updatedAt=utc_now(),
        sourceHandoff=source_handoff,
    )
