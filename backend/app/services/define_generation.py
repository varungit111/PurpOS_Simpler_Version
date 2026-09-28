import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    DefineApprovalStatus,
    DefineOutput,
    DefineProvenance,
    DefineState,
    DefineStatus,
    EvidenceStatus,
    IdentifyEvidence,
    PositioningStatement,
    SingleOrganizingIdeaCandidate,
    ValueChainMoment,
    ValueChainMomentStatus,
    ValueCommitment,
    utc_now,
)
from app.schemas.identify_completion import IdentifyHandoff
from app.services.ai_client import AIClient, AIClientError
from app.services.define_questions import deduplicate_define_questions
from app.stages.identify import identify_stage_config


DEFINE_HANDOFF_REFERENCE = "structured_outputs.identify.handoff"

SOI_EXCLUDED_ACTIVITIES = {
    "day-in-their-shoes",
    "signal-hunt",
    "where-do-you-stand",
}
SOI_EXCLUDED_TOPIC_CUES = (
    "claims performance",
    "financial strength",
    "market performance",
    "risk",
    "regulatory",
)
SOI_ACTION_PREFIXES = (
    "advance",
    "build",
    "care for",
    "connect",
    "create",
    "deliver",
    "enable",
    "help",
    "improve",
    "keep",
    "look after",
    "make",
    "protect",
    "serve",
    "strengthen",
    "support",
)
SOI_CONCEPT_STOP_WORDS = {
    "about",
    "across",
    "after",
    "always",
    "around",
    "business",
    "company",
    "entity",
    "group",
    "organisation",
    "organization",
    "provides",
    "service",
    "services",
    "through",
}
CATEGORY_EVIDENCE_AREAS = (
    "organisation_basics",
    "best_work",
    "market_position",
)
BENEFIT_EVIDENCE_AREAS = (
    "customer_needs",
    "best_work",
    "market_position",
    "purpose_driven_proof",
    "people_planet_stakeholders",
)
REASON_TO_BELIEVE_AREAS = (
    "performance_governance",
    "purpose_driven_proof",
    "market_position",
    "social_contribution",
    "people_planet_stakeholders",
    "best_work",
)
INTERNAL_TEMPLATE_PREFIXES = (
    "today the organisation leads with",
    "today the organization leads with",
    "contribution level:",
    "evidence items clustered",
    "selected company identity cards:",
)
CATEGORY_TOPIC_CUES = (
    "organisation",
    "organization",
    "business model",
    "company",
    "products",
    "services",
    "sector",
    "industry",
)
CATEGORY_IDENTITY_CUES = (
    " is a ",
    " is an ",
    " is the ",
    " are a ",
    " are an ",
    " are the ",
    "group of ",
    "provider of ",
    "provides ",
    "offers ",
    "insurer",
)
ANALYTICAL_EVIDENCE_CUES = (
    "market share",
    "claims-to-premium",
    "claims to premium",
    "claims ratio",
    "cost pressure",
    "vulnerability",
    "regulatory risk",
    "risk/opportunity",
    "trend",
)
BENEFIT_CUES = (
    "access",
    "benefit",
    "care",
    "cover",
    "delivers",
    "enables",
    "helps",
    "improves",
    "provides",
    "reliable",
    "service",
    "support",
    "wellbeing",
)
PROOF_CUES = (
    "award",
    "demonstrat",
    "documented",
    "financial strength",
    "members",
    "network",
    "operates",
    "outcomes",
    "paid",
    "rating",
    "returned",
    "scale",
)
RAW_ACTIVITY_CUES = (
    " should feel ",
    " may be a strength to preserve",
    "selected company identity cards:",
)
RELATION_STOP_WORDS = {
    "and",
    "because",
    "for",
    "from",
    "into",
    "more",
    "that",
    "the",
    "their",
    "this",
    "through",
    "with",
}


class DefineProposal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    soi_candidate: SingleOrganizingIdeaCandidate | None = Field(
        default=None,
        alias="soiCandidate",
    )
    positioning: PositioningStatement = Field(default_factory=PositioningStatement)
    values: list[ValueCommitment] = Field(default_factory=list)
    moments: list[ValueChainMoment] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(
        default_factory=list,
        alias="unresolvedQuestions",
    )
    evidence_references: list[UUID] = Field(
        default_factory=list,
        alias="evidenceReferences",
    )


def generate_define_state(
    handoff: IdentifyHandoff,
    *,
    ai_client: AIClient | None = None,
) -> DefineState:
    fallback_proposal = _fallback_proposal(handoff)
    proposal = fallback_proposal
    if ai_client is not None:
        ai_proposal = _ai_proposal(handoff, ai_client)
        if ai_proposal is not None:
            proposal = _merge_with_fallback(
                ai_proposal,
                fallback_proposal,
                organisation=handoff.brief.organisation_name,
                handoff=handoff,
            )

    evidence_ids = set(handoff.evidence_references)
    evidence_ids.update(handoff.strongest_evidence_ids)
    for item in handoff.output.positioning_evidence:
        evidence_ids.add(item.id)
    for item in handoff.output.social_contribution_evidence:
        evidence_ids.add(item.id)
    if proposal.soi_candidate is not None:
        evidence_ids.update(proposal.soi_candidate.evidence_ids)

    generated_at = utc_now()
    provenance = DefineProvenance(
        status=EvidenceStatus.ai_inferred,
        rationale=(
            "Define proposal generated from the persisted Identify handoff; "
            "content remains editable until the user agrees it."
        ),
        generatedAt=generated_at,
        sourceHandoff=DEFINE_HANDOFF_REFERENCE,
    )
    state = DefineState(
        assessmentId=handoff.assessment_id,
        status=DefineStatus.in_progress,
        sourceHandoff=DEFINE_HANDOFF_REFERENCE,
        soiCandidate=_with_provenance(proposal.soi_candidate, provenance),
        positioning=_with_provenance(proposal.positioning, provenance),
        values=[
            _with_provenance(value, provenance)
            for value in _dedupe_by_name(proposal.values)
        ],
        moments=[
            _with_provenance(moment, provenance)
            for moment in _dedupe_by_name(proposal.moments)
        ],
        unresolvedQuestions=deduplicate_define_questions(
            [*proposal.unresolved_questions, *handoff.open_questions]
        ),
        evidenceReferences=sorted(evidence_ids, key=str),
        provenance=provenance,
        output=None,
        createdAt=generated_at,
        updatedAt=generated_at,
    )
    state.output = build_define_output(state)
    return state


def has_usable_soi(state: DefineState) -> bool:
    candidate = state.soi_candidate
    return candidate is not None and _usable_soi_text(candidate.statement)


def has_complete_positioning(state: DefineState) -> bool:
    positioning = state.positioning
    return (
        _usable_positioning_text(positioning.audience, "audience")
        and _usable_positioning_text(positioning.category_context, "category_context")
        and _usable_positioning_text(positioning.capability_value, "capability_value")
        and _usable_positioning_text(
            positioning.reason_believability,
            "reason_believability",
        )
        and _usable_text(positioning.composed_statement)
    )


def repair_positioning(
    existing: PositioningStatement,
    generated: PositioningStatement,
    *,
    organisation: str,
) -> PositioningStatement:
    slot_updates = {
        field: (
            current
            if _usable_positioning_text(current, field)
            else getattr(generated, field)
        )
        for field, current in (
            ("audience", existing.audience),
            ("category_context", existing.category_context),
            ("capability_value", existing.capability_value),
            ("reason_believability", existing.reason_believability),
        )
    }
    slots_changed = any(
        slot_updates[field] != getattr(existing, field) for field in slot_updates
    )
    composed_statement = existing.composed_statement
    if slots_changed or not _usable_text(composed_statement):
        composed_statement = _compose_positioning(
            organisation,
            slot_updates["audience"],
            slot_updates["category_context"],
            slot_updates["capability_value"],
            slot_updates["reason_believability"],
        )
    return existing.model_copy(
        update={
            **slot_updates,
            "composed_statement": composed_statement,
            **(
                {
                    "evidence_ids": generated.evidence_ids,
                    "provenance": generated.provenance,
                }
                if slots_changed
                else {}
            ),
        },
        deep=True,
    )


def repair_value_meanings(
    values: list[ValueCommitment],
    fallback_values: list[ValueCommitment],
    *,
    handoff: IdentifyHandoff,
) -> list[ValueCommitment]:
    repaired: list[ValueCommitment] = []
    for value in values:
        if (
            value.approval_status != DefineApprovalStatus.ai_proposed
            or _usable_text(value.meaning)
        ):
            repaired.append(value)
            continue

        fallback = _matching_fallback_value(value, fallback_values)
        meaning = (
            fallback.meaning
            if fallback is not None and _usable_value_meaning(fallback.meaning)
            else None
        )
        if not _usable_value_meaning(meaning):
            meaning = _value_meaning_from_evidence(handoff, value.evidence_ids)
        if not _usable_value_meaning(meaning):
            repaired.append(value)
            continue

        repaired.append(
            value.model_copy(update={"meaning": meaning.strip()}, deep=True)
        )
    return repaired


def repair_moments(
    moments: list[ValueChainMoment],
    fallback_moments: list[ValueChainMoment],
    *,
    handoff: IdentifyHandoff,
) -> list[ValueChainMoment]:
    repaired: list[ValueChainMoment] = []
    for moment in moments:
        if (
            moment.approval_status != DefineApprovalStatus.ai_proposed
            or not _moment_needs_recovery(moment)
        ):
            repaired.append(moment)
            continue

        fallback = _matching_fallback_moment(moment, fallback_moments, handoff)
        updates: dict[str, Any] = {}
        for field in ("question", "today", "desired_state", "the_move"):
            current = getattr(moment, field)
            candidate = getattr(fallback, field) if fallback is not None else None
            if not _usable_moment_text(current) and _usable_moment_text(candidate):
                updates[field] = candidate.strip()

        if not _usable_supporting_evidence(moment.supporting_evidence):
            supporting_evidence = (
                _usable_supporting_evidence(fallback.supporting_evidence)
                if fallback is not None
                else []
            )
            if supporting_evidence:
                updates["supporting_evidence"] = supporting_evidence

        if fallback is not None:
            updates["status"] = fallback.status
        else:
            evidence_today, evidence_context = _moment_evidence_recovery(
                handoff,
                moment.evidence_ids,
            )
            if not _usable_moment_text(moment.today) and evidence_today is not None:
                updates["today"] = evidence_today
            if (
                not _usable_supporting_evidence(moment.supporting_evidence)
                and evidence_context
            ):
                updates["supporting_evidence"] = evidence_context

        repaired.append(
            moment.model_copy(update=updates, deep=True) if updates else moment
        )
    return repaired


def build_define_output(state: DefineState) -> DefineOutput:
    agreed_soi = (
        state.soi_candidate
        if state.soi_candidate is not None
        and state.soi_candidate.approval_status == DefineApprovalStatus.agreed
        else None
    )
    agreed_positioning = (
        state.positioning
        if state.positioning.approval_status == DefineApprovalStatus.agreed
        else None
    )
    return DefineOutput(
        agreedSoi=agreed_soi,
        agreedPositioning=agreed_positioning,
        agreedValues=[
            value
            for value in state.values
            if value.approval_status == DefineApprovalStatus.agreed
        ],
        agreedMoments=[
            moment
            for moment in state.moments
            if moment.approval_status == DefineApprovalStatus.agreed
        ],
        unresolvedQuestions=state.unresolved_questions,
        evidenceReferences=state.evidence_references,
        sourceHandoff=state.source_handoff,
        completionStatus=(
            state.status if state.status == DefineStatus.completed else None
        ),
        completedAt=(
            state.updated_at if state.status == DefineStatus.completed else None
        ),
        provenance=state.provenance,
    )


def _ai_proposal(
    handoff: IdentifyHandoff,
    ai_client: AIClient,
) -> DefineProposal | None:
    try:
        return ai_client.generate_structured(
            prompt=_proposal_prompt(handoff),
            output_schema=DefineProposal,
            system=(
                "You generate editable Define-stage proposals for PurpOS. "
                "Use only the supplied Identify handoff. Preserve evidence IDs. "
                "Do not mark anything agreed; the user is authoritative."
            ),
        )
    except AIClientError:
        return None


def _merge_with_fallback(
    proposal: DefineProposal,
    fallback: DefineProposal,
    *,
    organisation: str,
    handoff: IdentifyHandoff,
) -> DefineProposal:
    candidate = proposal.soi_candidate
    soi_candidate = (
        candidate
        if candidate is not None and _usable_soi_text(candidate.statement)
        else fallback.soi_candidate
    )
    return proposal.model_copy(
        update={
            "soi_candidate": soi_candidate,
            "positioning": repair_positioning(
                proposal.positioning,
                fallback.positioning,
                organisation=organisation,
            ),
            "values": repair_value_meanings(
                proposal.values,
                fallback.values,
                handoff=handoff,
            ),
            "moments": repair_moments(
                proposal.moments,
                fallback.moments,
                handoff=handoff,
            ),
        },
        deep=True,
    )


def _proposal_prompt(handoff: IdentifyHandoff) -> str:
    return (
        "Create a Define proposal from this Identify handoff. Include a "
        "Single Organizing Idea candidate, Positioning Statement scaffold, "
        "Values/commitments, and Value Chain/Moments of Truth only where "
        "supported by the handoff evidence. Every Value must include a concise "
        "plain-language meaning grounded in its referenced evidence. For each "
        "Moment of Truth, provide an assessment-specific question, current state, "
        "desired state, supporting evidence, and an opportunity or move only when "
        "the evidence supports it. Set operational status from evidenced gaps, "
        "moves, or an on-course current state, never from approval state. Do not "
        "invent unsupported content; null is acceptable when evidence genuinely "
        "does not support a Moment field.\n\n"
        f"{handoff.model_dump_json(by_alias=True)}"
    )


def _fallback_proposal(handoff: IdentifyHandoff) -> DefineProposal:
    organisation = handoff.brief.organisation_name
    positioning_evidence = handoff.output.positioning_evidence
    social_evidence = handoff.output.social_contribution_evidence
    strongest_ids = handoff.strongest_evidence_ids or handoff.evidence_references

    soi_statement, soi_meaning, soi_evidence = _synthesize_soi(handoff)

    values = [
        ValueCommitment(
            name=theme.name,
            meaning=theme.summary,
            supportingEvidence=[
                evidence.claim
                for evidence in _evidence_for_ids(handoff, theme.evidence_ids)
            ],
            evidenceIds=theme.evidence_ids,
        )
        for theme in handoff.brief.themes[:4]
    ]
    if not values and social_evidence:
        values = [
            ValueCommitment(
                name=_short_label(item.claim),
                meaning=item.summary or item.claim,
                supportingEvidence=[item.claim],
                evidenceIds=[item.id],
            )
            for item in social_evidence[:4]
        ]

    moments = _moments_from_journeys(handoff)
    if not moments:
        moments = [
            ValueChainMoment(
                name=area.label,
                question=area.question,
                today=_claim_summary(handoff, area.evidence_ids),
                desiredState=None,
                theMove=None,
                status=(
                    ValueChainMomentStatus.gap_to_close
                    if area.status == "uncovered"
                    else ValueChainMomentStatus.in_progress
                    if area.status == "partial"
                    else ValueChainMomentStatus.on_course
                ),
                supportingEvidence=[
                    evidence.claim
                    for evidence in _evidence_for_ids(handoff, area.evidence_ids)
                ],
                evidenceIds=area.evidence_ids,
            )
            for area in handoff.coverage
            if area.evidence_ids
        ][:7]

    audience = _first_stakeholder_name(handoff)
    category_evidence = select_category_evidence(handoff)
    benefit_evidence = select_benefit_evidence(
        handoff,
        excluded_ids={item.id for item in category_evidence},
    )
    reason_evidence = select_reason_to_believe_evidence(
        handoff,
        benefit_evidence=benefit_evidence,
        excluded_ids={item.id for item in benefit_evidence},
    )
    category_context = _category_evidence_text(
        category_evidence,
        organisation=organisation,
    ) or organisation
    capability_value = _benefit_evidence_text(
        benefit_evidence,
        organisation=organisation,
    )
    reason_believability = _reason_evidence_text(reason_evidence)
    positioning_ids = _unique_ids(
        [
            *[item.id for item in category_evidence],
            *[item.id for item in benefit_evidence],
            *[item.id for item in reason_evidence],
        ]
    ) or [item.id for item in positioning_evidence] or strongest_ids[:3]

    fallback_provenance = DefineProvenance(
        status=EvidenceStatus.source_derived,
        rationale=(
            "Define fallback derived deterministically from role-matched "
            "Identify evidence."
        ),
        sourceHandoff=DEFINE_HANDOFF_REFERENCE,
    )
    positioning = PositioningStatement(
        audience=audience,
        categoryContext=category_context,
        capabilityValue=capability_value,
        reasonBelievability=reason_believability,
        composedStatement=_compose_positioning(
            organisation,
            audience,
            category_context,
            capability_value,
            reason_believability,
        ),
        evidenceIds=positioning_ids,
        provenance=fallback_provenance,
    )

    return DefineProposal(
        soiCandidate=SingleOrganizingIdeaCandidate(
            statement=soi_statement,
            guidingStar=soi_statement,
            meaning=soi_meaning,
            evidenceIds=[item.id for item in soi_evidence],
            provenance=fallback_provenance,
        ),
        positioning=positioning,
        values=values,
        moments=moments,
        unresolvedQuestions=handoff.open_questions,
        evidenceReferences=handoff.evidence_references,
    )


def _moments_from_journeys(handoff: IdentifyHandoff) -> list[ValueChainMoment]:
    moments: list[ValueChainMoment] = []
    for journey in handoff.output.stakeholder_journeys:
        for touchpoint in journey.touchpoints:
            evidence_ids: list[UUID] = []
            today = _first_or_none(
                [experience.summary for experience in touchpoint.observed_experiences]
            )
            desired_state = _first_or_none(
                [expectation.summary for expectation in touchpoint.expectations]
            )
            the_move = _first_or_none(
                [opportunity.summary for opportunity in touchpoint.opportunities]
            )
            status = (
                ValueChainMomentStatus.gap_to_close
                if touchpoint.gaps
                else ValueChainMomentStatus.in_progress
                if the_move
                else ValueChainMomentStatus.on_course
            )
            moments.append(
                ValueChainMoment(
                    name=touchpoint.moment,
                    question=(
                        f"What should {journey.stakeholder_name} experience at "
                        f"{touchpoint.moment}?"
                    ),
                    today=today,
                    desiredState=desired_state,
                    theMove=the_move,
                    status=status,
                    supportingEvidence=touchpoint.supporting_evidence,
                    evidenceIds=evidence_ids,
                )
            )
    return moments[:7]


def _with_provenance(item, provenance: DefineProvenance):
    if item is None:
        return None
    item_provenance = item.provenance
    if (
        item_provenance.status != EvidenceStatus.ai_inferred
        or item_provenance.rationale
    ):
        provenance = item_provenance.model_copy(
            update={
                "generated_at": item_provenance.generated_at or provenance.generated_at,
                "source_handoff": item_provenance.source_handoff
                or provenance.source_handoff,
            },
            deep=True,
        )
    return item.model_copy(
        update={
            "provenance": provenance,
            "approval_status": DefineApprovalStatus.ai_proposed,
        },
        deep=True,
    )


def _dedupe_by_name(items):
    seen: set[str] = set()
    deduped = []
    for item in items:
        name = item.name.strip().lower()
        if name in seen:
            continue
        seen.add(name)
        deduped.append(item)
    return deduped


def _evidence_for_ids(
    handoff: IdentifyHandoff,
    evidence_ids: list[UUID],
) -> list[Any]:
    by_id = {item.id: item for item in _all_identify_evidence(handoff)}
    return [by_id[item_id] for item_id in evidence_ids if item_id in by_id]


def _all_identify_evidence(handoff: IdentifyHandoff) -> list[Any]:
    by_id: dict[UUID, Any] = {}
    for item in [
        *handoff.output.positioning_evidence,
        *handoff.output.social_contribution_evidence,
        *handoff.brief.strongest_evidence,
    ]:
        by_id[item.id] = item
    return list(by_id.values())


def _all_value_evidence(handoff: IdentifyHandoff) -> list[Any]:
    by_id: dict[UUID, Any] = {}
    for item in [
        *handoff.output.research_findings,
        *handoff.output.pestle_findings,
        *_all_identify_evidence(handoff),
    ]:
        by_id[item.id] = item
    return list(by_id.values())


def _matching_fallback_value(
    value: ValueCommitment,
    fallback_values: list[ValueCommitment],
) -> ValueCommitment | None:
    value_evidence = set(value.evidence_ids)
    overlap_matches = [
        (len(value_evidence.intersection(fallback.evidence_ids)), fallback)
        for fallback in fallback_values
    ]
    best_overlap = max((score for score, _ in overlap_matches), default=0)
    if best_overlap:
        best = [
            fallback
            for score, fallback in overlap_matches
            if score == best_overlap
        ]
        if len(best) == 1:
            return best[0]

    value_tokens = _meaningful_name_tokens(value.name)
    name_matches = [
        fallback
        for fallback in fallback_values
        if _names_reliably_match(
            value.name,
            value_tokens,
            fallback.name,
            _meaningful_name_tokens(fallback.name),
        )
    ]
    return name_matches[0] if len(name_matches) == 1 else None


def _matching_fallback_moment(
    moment: ValueChainMoment,
    fallback_moments: list[ValueChainMoment],
    handoff: IdentifyHandoff,
) -> ValueChainMoment | None:
    moment_evidence = set(moment.evidence_ids)
    overlap_matches = [
        (len(moment_evidence.intersection(fallback.evidence_ids)), fallback)
        for fallback in fallback_moments
    ]
    best_overlap = max((score for score, _ in overlap_matches), default=0)
    if best_overlap:
        best = [
            fallback
            for score, fallback in overlap_matches
            if score == best_overlap
        ]
        if len(best) == 1:
            return best[0]

    name_matches = [
        fallback
        for fallback in fallback_moments
        if _moment_names_reliably_match(moment.name, fallback.name)
    ]
    if len(name_matches) == 1:
        return name_matches[0]

    source_names = {
        touchpoint.moment
        for journey in handoff.output.stakeholder_journeys
        for touchpoint in journey.touchpoints
        if touchpoint.id in moment_evidence
    }
    source_matches = [
        fallback
        for fallback in fallback_moments
        if any(
            _moment_names_reliably_match(fallback.name, source_name)
            for source_name in source_names
        )
    ]
    return source_matches[0] if len(source_matches) == 1 else None


def _moment_names_reliably_match(left: str, right: str) -> bool:
    ignored = {"getting", "generation"}
    left_tokens = _meaningful_name_tokens(left) - ignored
    right_tokens = _meaningful_name_tokens(right) - ignored
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens.intersection(right_tokens)
    return bool(shared) and (
        shared == left_tokens or shared == right_tokens or len(shared) >= 2
    )


def _moment_needs_recovery(moment: ValueChainMoment) -> bool:
    return (
        any(
            not _usable_moment_text(value)
            for value in (
                moment.question,
                moment.today,
                moment.desired_state,
                moment.the_move,
            )
        )
        or not _usable_supporting_evidence(moment.supporting_evidence)
    )


def _usable_moment_text(value: str | None) -> bool:
    return (
        _usable_evidence_text(value)
        and not _is_internal_or_area_label(value)
    )


def _usable_moment_source_text(value: str | None) -> bool:
    return _usable_moment_text(value) and not _is_raw_activity_text(value)


def _usable_supporting_evidence(items: list[str]) -> list[str]:
    return [
        item.strip()
        for item in items
        if _usable_moment_source_text(item) and len(item.strip().split()) >= 2
    ]


def _moment_evidence_recovery(
    handoff: IdentifyHandoff,
    evidence_ids: list[UUID],
) -> tuple[str | None, list[str]]:
    by_id = {item.id: item for item in _all_value_evidence(handoff)}
    context: list[str] = []
    for evidence_id in evidence_ids:
        item = by_id.get(evidence_id)
        if item is None:
            continue
        candidates = (
            [getattr(item, "description", None), getattr(item, "signal", None)]
            if hasattr(item, "description")
            else [getattr(item, "summary", None), getattr(item, "claim", None)]
        )
        for candidate in candidates:
            if (
                _usable_moment_source_text(candidate)
                and len(candidate.strip().split()) >= 4
            ):
                concise = _concise_evidence_text(candidate)
                if concise not in context:
                    context.append(concise)
                break
    return (context[0] if context else None, context)


def _meaningful_name_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in RELATION_STOP_WORDS
    }


def _names_reliably_match(
    left: str,
    left_tokens: set[str],
    right: str,
    right_tokens: set[str],
) -> bool:
    if _normalize_label(left) == _normalize_label(right):
        return True
    shared = left_tokens.intersection(right_tokens)
    return bool(shared) and (
        shared == left_tokens or shared == right_tokens or len(shared) >= 2
    )


def _value_meaning_from_evidence(
    handoff: IdentifyHandoff,
    evidence_ids: list[UUID],
) -> str | None:
    by_id = {item.id: item for item in _all_value_evidence(handoff)}
    for evidence_id in evidence_ids:
        item = by_id.get(evidence_id)
        if item is None:
            continue
        candidates = (
            [getattr(item, "description", None), getattr(item, "why_it_matters", None)]
            if hasattr(item, "description")
            else [getattr(item, "summary", None), getattr(item, "claim", None)]
        )
        for candidate in candidates:
            if _usable_value_meaning(candidate):
                return _concise_evidence_text(candidate)
    return None


def _usable_value_meaning(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return (
        _usable_evidence_text(value)
        and len(value.strip().split()) >= 4
        and not _is_internal_or_area_label(value)
        and not _is_raw_activity_text(value)
        and "evidence items clustered" not in normalized
        and "evidence wall" not in normalized
    )


def _concise_evidence_text(value: str) -> str:
    text = " ".join(value.strip().split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    concise = " ".join(sentences[:2])
    if len(concise) <= 360:
        return concise
    shortened = concise[:357].rsplit(" ", 1)[0]
    return f"{shortened.rstrip('.,;:')}..."


def _claim_summary(handoff: IdentifyHandoff, evidence_ids: list[UUID]) -> str | None:
    evidence = _evidence_for_ids(handoff, evidence_ids)
    return evidence[0].summary or evidence[0].claim if evidence else None


def select_soi_evidence(handoff: IdentifyHandoff) -> list[Any]:
    candidates: list[Any] = []
    company_cards = handoff.output.company_cards_evidence
    if company_cards is not None:
        candidates.append(company_cards)
    candidates.extend(handoff.output.research_findings)
    candidates.extend(_all_identify_evidence(handoff))

    by_id: dict[UUID, Any] = {}
    for item in candidates:
        if _usable_soi_source(item):
            by_id[item.id] = item
    return list(by_id.values())


def _synthesize_soi(
    handoff: IdentifyHandoff,
) -> tuple[str, str, list[Any]]:
    organisation = handoff.brief.organisation_name
    candidates = select_soi_evidence(handoff)
    phrase_source: Any | None = None
    statement: str | None = None
    for item in candidates:
        phrase = _soi_phrase_from_source(item, organisation)
        if phrase is not None:
            phrase_source = item
            statement = phrase
            break

    if statement is None or phrase_source is None:
        return (
            organisation,
            (
                "The available evidence confirms the organisation identity but "
                "does not yet support a more distinctive organising idea."
            ),
            [],
        )

    supporting = _select_soi_support(statement, phrase_source, candidates)
    return statement, _soi_rationale(statement, supporting), supporting


def _usable_soi_source(item: Any) -> bool:
    text = _soi_source_text(item)
    if text is None:
        return False
    if (
        _is_internal_or_area_label(text)
        or _is_template_artifact(text)
        or _is_raw_activity_text(text)
        or _is_analytical_evidence(text)
    ):
        return False
    source_activity = str(getattr(item, "source_activity", "") or "").lower()
    if source_activity in SOI_EXCLUDED_ACTIVITIES:
        return False
    topic = _item_topic(item)
    if any(cue in topic for cue in SOI_EXCLUDED_TOPIC_CUES):
        return False
    return not _looks_like_numeric_proof(_first_sentence(text))


def _soi_source_text(item: Any) -> str | None:
    for value in (
        getattr(item, "explanation", None),
        getattr(item, "claim", None),
        getattr(item, "summary", None),
    ):
        if _usable_text(value):
            return value.strip()
    return None


def _soi_phrase_from_source(item: Any, organisation: str) -> str | None:
    text = _soi_source_text(item)
    if text is None:
        return None
    sentence = _strip_organisation_subject(_first_sentence(text), organisation)
    normalized = sentence.lower().strip()
    for action in SOI_ACTION_PREFIXES:
        forms = (action, f"{action}s")
        matched = next(
            (form for form in forms if normalized.startswith(f"{form} ")),
            None,
        )
        if matched is None:
            continue
        remainder = sentence[len(matched) :].strip().split(" rather than ", 1)[0]
        phrase = f"{action} {remainder}".rstrip(" .")
        if action == "look after":
            phrase = _add_simple_possessive(phrase)
        return phrase[0].upper() + phrase[1:] if phrase else None

    priority_match = re.search(
        r"\bpriority to (.+?)(?:\s+rather than|[.;]|$)",
        sentence,
        flags=re.IGNORECASE,
    )
    if priority_match:
        focus = priority_match.group(1).strip()
        return f"Put {focus} first"
    return None


def _add_simple_possessive(phrase: str) -> str:
    prefix = "look after "
    remainder = phrase[len(prefix) :]
    words = remainder.split()
    if len(words) == 2 and words[0].lower().endswith("s"):
        words[0] = f"{words[0]}'"
    return f"{prefix}{' '.join(words)}"


def _select_soi_support(
    statement: str,
    phrase_source: Any,
    candidates: list[Any],
) -> list[Any]:
    statement_words = _soi_content_words(statement)
    related = [
        item
        for item in candidates
        if item.id != phrase_source.id
        and statement_words & _soi_content_words(_soi_source_text(item) or "")
    ]
    related.sort(
        key=lambda item: len(
            statement_words & _soi_content_words(_soi_source_text(item) or "")
        ),
        reverse=True,
    )
    return [phrase_source, *related[:2]]


def _soi_content_words(text: str) -> set[str]:
    return {
        _word_key(word)
        for word in re.findall(r"[a-z]{4,}", text.lower())
        if word not in RELATION_STOP_WORDS
        and word not in SOI_CONCEPT_STOP_WORDS
        and not any(
            word.startswith(action.split()[0]) for action in SOI_ACTION_PREFIXES
        )
    }


def _soi_rationale(statement: str, supporting: list[Any]) -> str:
    concept = statement.lower()
    for action in SOI_ACTION_PREFIXES:
        if concept.startswith(f"{action} "):
            concept = concept[len(action) + 1 :]
            break
    descriptions = sorted(
        {
            description
            for item in supporting
            if (description := _soi_source_description(item)) is not None
        },
        key=_soi_description_rank,
    )
    evidence_context = _join_phrases(descriptions[:2]) or "the assessment evidence"
    recurring = "recurring " if len(supporting) > 1 else ""
    return (
        f"This idea emerged from a {recurring}focus on {concept} across "
        f"{evidence_context}. It turns that supported commitment into a practical "
        "reference point for decisions and connects organisational intent with "
        "stakeholder value."
    )


def _soi_source_description(item: Any) -> str | None:
    topic = _item_topic(item)
    area_ids = set(_coverage_area_ids(item))
    if any(cue in topic for cue in ("organisation", "organization", "business model")):
        return "organisation identity"
    if any(cue in topic for cue in ("products", "services")):
        return "products and services"
    if any(cue in topic for cue in ("community", "social")):
        return "community contribution"
    if "founding_story" in area_ids:
        return "the founding story"
    if "purpose_driven_proof" in area_ids:
        return "purpose-driven proof"
    if "customer_needs" in area_ids:
        return "customer evidence"
    if "best_work" in area_ids:
        return "evidence of the organisation at its best"
    return None


def _soi_description_rank(description: str) -> int:
    order = (
        "organisation identity",
        "the founding story",
        "customer evidence",
        "products and services",
        "purpose-driven proof",
        "community contribution",
        "evidence of the organisation at its best",
    )
    return order.index(description) if description in order else len(order)


def _join_phrases(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return f"{values[0]} and {values[1]}"


def select_category_evidence(handoff: IdentifyHandoff) -> list[Any]:
    candidates = [
        item
        for item in _positioning_evidence_candidates(handoff)
        if _category_text(item, handoff.brief.organisation_name) is not None
    ]
    return sorted(
        candidates,
        key=lambda item: _category_rank(
            item,
            handoff.brief.organisation_name,
            handoff.strongest_evidence_ids,
        ),
        reverse=True,
    )[:1]


def select_benefit_evidence(
    handoff: IdentifyHandoff,
    *,
    excluded_ids: set[UUID] | None = None,
) -> list[Any]:
    excluded_ids = excluded_ids or set()
    candidates = [
        item
        for item in _positioning_evidence_candidates(handoff)
        if item.id not in excluded_ids and _benefit_text(item) is not None
    ]
    return sorted(
        candidates,
        key=lambda item: _benefit_rank(item, handoff.strongest_evidence_ids),
        reverse=True,
    )[:1]


def select_reason_to_believe_evidence(
    handoff: IdentifyHandoff,
    *,
    benefit_evidence: list[Any] | None = None,
    excluded_ids: set[UUID] | None = None,
) -> list[Any]:
    excluded_ids = excluded_ids or set()
    all_candidates = [
        item
        for item in _positioning_evidence_candidates(handoff)
        if item.id not in excluded_ids
    ]
    candidates = [item for item in all_candidates if _reason_text(item) is not None]
    if not candidates:
        candidates = [
            item
            for item in all_candidates
            if _reason_text(item, require_proof=False) is not None
        ]
    benefit_text = _first_evidence_text(benefit_evidence or [])
    return sorted(
        candidates,
        key=lambda item: _reason_rank(
            item,
            benefit_text,
            handoff.strongest_evidence_ids,
        ),
        reverse=True,
    )[:1]


def _positioning_evidence_candidates(handoff: IdentifyHandoff) -> list[Any]:
    by_id = {item.id: item for item in _all_identify_evidence(handoff)}
    for item in handoff.output.research_findings:
        by_id[item.id] = item
    return list(by_id.values())


def _category_rank(
    item: Any,
    organisation: str,
    strongest_ids: list[UUID],
) -> tuple[int, int, int, int, int]:
    topic = _item_topic(item)
    text = _evidence_text(item) or ""
    normalized = f" {text.lower()} "
    area_ids = set(_coverage_area_ids(item))
    return (
        _category_topic_rank(topic),
        1 if any(cue in normalized for cue in CATEGORY_IDENTITY_CUES) else 0,
        1 if "organisation_basics" in area_ids else 0,
        1 if item.id in strongest_ids else 0,
        -len(_category_text(item, organisation) or text),
    )


def _category_topic_rank(topic: str) -> int:
    if any(
        cue in topic
        for cue in ("organisation", "organization", "business model", "company")
    ):
        return 2
    if any(cue in topic for cue in ("products", "services", "sector", "industry")):
        return 1
    return 0


def _benefit_rank(
    item: Any,
    strongest_ids: list[UUID],
) -> tuple[int, int, int, int, int]:
    text = (_benefit_text(item) or "").lower()
    topic = _item_topic(item)
    area_ids = set(_coverage_area_ids(item))
    return (
        _benefit_subject_rank(text),
        1 if "customer_needs" in area_ids else 0,
        1 if any(cue in topic for cue in ("products", "services", "customer")) else 0,
        sum(cue in text for cue in BENEFIT_CUES),
        1 if item.id in strongest_ids else 0,
    )


def _benefit_subject_rank(text: str) -> int:
    return int(
        bool(
            re.search(
                r"\b(?:provides|offers|delivers|helps|enables|improves|supports)\b",
                text,
            )
        )
        and not text.startswith(("adoption ", "demand ", "market ", "trend "))
    )


def _reason_rank(
    item: Any,
    benefit_text: str | None,
    strongest_ids: list[UUID],
) -> tuple[int, int, int, int]:
    text = (_reason_text(item, require_proof=False) or "").lower()
    area_ids = set(_coverage_area_ids(item))
    return (
        _shared_meaningful_word_count(text, benefit_text),
        sum(cue in text for cue in PROOF_CUES)
        + int(any(char.isdigit() for char in text)),
        len(area_ids & set(REASON_TO_BELIEVE_AREAS)),
        1 if item.id in strongest_ids else 0,
    )


def _category_evidence_text(
    items: list[Any],
    *,
    organisation: str,
) -> str | None:
    return next(
        (
            text
            for item in items
            if (text := _category_text(item, organisation)) is not None
        ),
        None,
    )


def _benefit_evidence_text(
    items: list[Any],
    *,
    organisation: str,
) -> str | None:
    text = next(
        (text for item in items if (text := _benefit_text(item)) is not None),
        None,
    )
    if not text:
        return None
    return _clean_slot_text(_strip_organisation_subject(text, organisation))


def _reason_evidence_text(items: list[Any]) -> str | None:
    text = next(
        (
            text
            for item in items
            if (text := _reason_text(item, require_proof=False)) is not None
        ),
        None,
    )
    return _clean_slot_text(text) if text else None


def _category_text(item: Any, organisation: str) -> str | None:
    text = _evidence_text(item)
    if text is None or _is_analytical_evidence(text) or _is_raw_activity_text(text):
        return None
    topic = _item_topic(item)
    normalized = f" {text.lower()} "
    area_ids = set(_coverage_area_ids(item))
    has_category_signal = (
        any(cue in topic for cue in CATEGORY_TOPIC_CUES)
        or any(cue in normalized for cue in CATEGORY_IDENTITY_CUES)
        or "organisation_basics" in area_ids
    )
    if not has_category_signal or (
        "organisation_basics" not in area_ids and not topic
    ):
        return None

    sentence = _first_sentence(text)
    identity_match = re.search(
        r"\b(?:is|are)\s+(?:an?\s+|the\s+)?(.+)$",
        sentence,
        flags=re.IGNORECASE,
    )
    if identity_match:
        sentence = identity_match.group(1)
    else:
        subject_stripped = _strip_organisation_subject(sentence, organisation)
        provides_match = re.match(
            r"(?:provides|offers)\s+(.+)$",
            subject_stripped,
            flags=re.IGNORECASE,
        )
        if provides_match:
            sentence = f"provider of {provides_match.group(1)}"
        else:
            sentence = subject_stripped
    sentence = re.sub(r"^(?:an?|the)\s+", "", sentence, flags=re.IGNORECASE)
    return sentence.rstrip(" .") or None


def _benefit_text(item: Any) -> str | None:
    text = _evidence_text(item)
    if text is None or _is_analytical_evidence(text) or _is_raw_activity_text(text):
        return None
    topic = _item_topic(item)
    area_ids = set(_coverage_area_ids(item))
    normalized = text.lower()
    role_supported = bool(
        area_ids & set(BENEFIT_EVIDENCE_AREAS)
        or any(cue in topic for cue in ("products", "services", "customer"))
    )
    if not role_supported or not any(cue in normalized for cue in BENEFIT_CUES):
        return None
    return _first_sentence(text)


def _reason_text(item: Any, *, require_proof: bool = True) -> str | None:
    text = _evidence_text(item)
    if text is None or _is_raw_activity_text(text):
        return None
    topic = _item_topic(item)
    area_ids = set(_coverage_area_ids(item))
    normalized = text.lower()
    role_supported = bool(
        area_ids & set(REASON_TO_BELIEVE_AREAS)
        or any(
            cue in topic
            for cue in ("performance", "reputation", "strength", "outcome", "scale")
        )
    )
    has_proof = any(cue in normalized for cue in PROOF_CUES) or any(
        char.isdigit() for char in text
    )
    return (
        _first_sentence(text)
        if role_supported and (has_proof or not require_proof)
        else None
    )


def _item_topic(item: Any) -> str:
    return str(getattr(item, "topic", "") or "").lower()


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0].strip()


def _clean_slot_text(text: str) -> str:
    return text.strip().rstrip(" .")


def _strip_organisation_subject(text: str, organisation: str) -> str:
    stripped = text.strip()
    names = [organisation, *organisation.rsplit(" ", 1)[:1]]
    for name in sorted(set(names), key=len, reverse=True):
        prefix = re.compile(rf"^{re.escape(name)}\s+", flags=re.IGNORECASE)
        if prefix.match(stripped):
            return prefix.sub("", stripped, count=1)
    return stripped


def _is_analytical_evidence(text: str) -> bool:
    normalized = text.lower()
    return any(cue in normalized for cue in ANALYTICAL_EVIDENCE_CUES)


def _is_raw_activity_text(text: str) -> bool:
    normalized = text.lower()
    return any(cue in normalized for cue in RAW_ACTIVITY_CUES)


def _is_benefit_without_proof(text: str) -> bool:
    normalized = text.lower().strip()
    states_outcome = normalized.startswith(
        ("adoption of ", "use of ", "using ")
    ) and any(cue in normalized for cue in ("improves", "enables", "reduces"))
    has_proof = any(cue in normalized for cue in PROOF_CUES) or any(
        char.isdigit() for char in text
    )
    return states_outcome and not has_proof


def _shared_meaningful_word_count(
    first: str,
    second: str | None,
) -> int:
    if not second:
        return 0
    first_words = {
        _word_key(word)
        for word in re.findall(r"[a-z]{4,}", first.lower())
        if word not in RELATION_STOP_WORDS
    }
    second_words = {
        _word_key(word)
        for word in re.findall(r"[a-z]{4,}", second.lower())
        if word not in RELATION_STOP_WORDS
    }
    return len(first_words & second_words)


def _word_key(word: str) -> str:
    if word.startswith("healthcare"):
        return "health"
    if word.startswith("cover"):
        return "cover"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _first_evidence_text(items: list[Any]) -> str | None:
    for item in items:
        text = _evidence_text(item)
        if text is not None:
            return text
    return None


def _evidence_text(item: Any) -> str | None:
    for value in (getattr(item, "claim", None), getattr(item, "summary", None)):
        if _usable_evidence_text(value):
            return value.strip()
    return None


def _coverage_area_ids(item: Any) -> list[str]:
    return list(getattr(item, "coverage_area_ids", []) or [])


def _first_or_none(items: list[str]) -> str | None:
    return next((item for item in items if item.strip()), None)


def _first_stakeholder_name(handoff: IdentifyHandoff) -> str | None:
    stakeholders = handoff.output.stakeholder_insights
    if not stakeholders:
        return handoff.brief.organisation_name
    customer = next(
        (item for item in stakeholders if item.group_type == "customer"),
        None,
    )
    external = next(
        (item for item in stakeholders if item.internal_or_external == "external"),
        None,
    )
    return (customer or external or stakeholders[0]).name


def _short_label(text: str) -> str:
    words = text.replace(".", "").split()
    return " ".join(words[:4]) if words else "Evidence-backed commitment"


def _compose_positioning(
    organisation: str,
    audience: str | None,
    category_context: str | None,
    capability_value: str | None,
    reason_believability: str | None,
) -> str | None:
    if not all(
        _usable_text(value)
        for value in (
            audience,
            category_context,
            capability_value,
            reason_believability,
        )
    ):
        return None
    return (
        f"For {audience}, {organisation} is the {category_context} that "
        f"{capability_value} - because {reason_believability}"
    )


def _usable_text(value: str | None) -> bool:
    return bool((value or "").strip())


def _usable_soi_text(value: str | None) -> bool:
    if not _usable_text(value):
        return False
    return not (
        _is_internal_or_area_label(value)
        or _is_template_artifact(value)
        or _is_raw_activity_text(value)
        or _is_analytical_evidence(value)
        or _looks_like_numeric_proof(value)
    )


def _looks_like_numeric_proof(value: str) -> bool:
    return bool(re.search(r"\d|[%$£€]", value))


def _usable_positioning_text(value: str | None, field: str) -> bool:
    if not _usable_text(value):
        return False
    if _is_template_artifact(value):
        return False
    if field == "category_context" and _is_internal_or_area_label(value):
        return False
    if field in {"category_context", "capability_value"} and (
        _is_analytical_evidence(value) or _is_raw_activity_text(value)
    ):
        return False
    if field == "reason_believability" and _is_benefit_without_proof(value):
        return False
    return True


def _usable_evidence_text(value: str | None) -> bool:
    return _usable_text(value) and not _is_template_artifact(value)


def _is_internal_or_area_label(value: str | None) -> bool:
    if not _usable_text(value):
        return False
    normalized = _normalize_label(value)
    return normalized in _known_internal_labels()


def _is_template_artifact(value: str | None) -> bool:
    if not _usable_text(value):
        return False
    text = value.strip().lower()
    return any(text.startswith(prefix) for prefix in INTERNAL_TEMPLATE_PREFIXES)


def _known_internal_labels() -> set[str]:
    labels = {
        _normalize_label(area.label)
        for area in identify_stage_config.question_evidence_areas
    }
    labels.update(
        {
            "current positioning",
            "social contribution",
            "where do you stand",
        }
    )
    return labels


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _unique_ids(values: list[UUID]) -> list[UUID]:
    unique: list[UUID] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique
