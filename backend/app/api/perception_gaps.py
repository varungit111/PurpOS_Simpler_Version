from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.config.identify_dependencies import (
    PERCEPTION_GAPS_DEPENDENCY,
    count_meaningful_identify_evidence_sources,
)
from app.schemas.assessment import IdentifyState, PerceptionGap
from app.schemas.perception_gaps import (
    EvidenceReference,
    PerceptionGapProgress,
    PerceptionGapReviewRequest,
    PerceptionGapsResponse,
    PerceptionGapsUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["perception-gaps"])

@router.get(
    "/{session_id}/identify/perception-gaps",
    response_model=PerceptionGapsResponse,
)
def get_perception_gaps(session_id: UUID) -> PerceptionGapsResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state)


@router.put(
    "/{session_id}/identify/perception-gaps",
    response_model=PerceptionGapsResponse,
)
def update_perception_gaps(
    session_id: UUID, payload: PerceptionGapsUpdateRequest
) -> PerceptionGapsResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()
    if not PERCEPTION_GAPS_DEPENDENCY.is_satisfied(state):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=PERCEPTION_GAPS_DEPENDENCY.locked_message,
        )

    _validate_supporting_evidence(state, payload.gaps)
    updated = session_store.update_identify_perception_gaps(
        session_id=session_id,
        gaps=payload.gaps,
    )
    if updated is None:
        raise _session_not_found()

    return _response(updated, message="Perception gaps saved.")


@router.patch(
    "/{session_id}/identify/perception-gaps/{gap_id}",
    response_model=PerceptionGapsResponse,
)
def review_perception_gap(
    session_id: UUID,
    gap_id: UUID,
    payload: PerceptionGapReviewRequest,
) -> PerceptionGapsResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()
    if not PERCEPTION_GAPS_DEPENDENCY.is_satisfied(state):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=PERCEPTION_GAPS_DEPENDENCY.locked_message,
        )

    gaps = [
        _reviewed_gap(gap, payload) if gap.id == gap_id else gap
        for gap in state.output.perception_gaps
    ]
    if all(gap.id != gap_id for gap in state.output.perception_gaps):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perception gap not found.",
        )

    updated = session_store.update_identify_perception_gaps(
        session_id=session_id,
        gaps=gaps,
    )
    if updated is None:
        raise _session_not_found()

    return _response(updated, message="Perception gap review saved.")


def _reviewed_gap(
    gap: PerceptionGap,
    payload: PerceptionGapReviewRequest,
) -> PerceptionGap:
    return gap.model_copy(
        update={
            "resolution": payload.resolution,
            "perspective_a": payload.perspective_a or gap.perspective_a,
            "perspective_b": payload.perspective_b or gap.perspective_b,
            "difference": payload.difference or gap.difference,
            "clarification_needed": (
                payload.clarification_needed
                if payload.clarification_needed is not None
                else False
            ),
            "resolution_note": payload.resolution_note or gap.resolution_note,
        }
    )


def _validate_supporting_evidence(
    state: IdentifyState,
    gaps: list[PerceptionGap],
) -> None:
    evidence_ids = {reference.id for reference in _evidence_references(state)}
    for gap in gaps:
        if any(
            evidence_id not in evidence_ids
            for evidence_id in gap.supporting_evidence_ids
        ):
            raise HTTPException(
                status_code=422,
                detail="Each perception gap must reference known Identify evidence.",
            )


def _response(
    state: IdentifyState,
    message: str | None = None,
) -> PerceptionGapsResponse:
    evidence_references = _evidence_references(state)
    source_count = count_meaningful_identify_evidence_sources(state)
    required_count = PERCEPTION_GAPS_DEPENDENCY.minimum_sources or 1
    unlocked = PERCEPTION_GAPS_DEPENDENCY.is_satisfied(state)
    gap_count = len(state.output.perception_gaps)
    label = (
        f"{source_count}/{required_count} evidence sources"
        if not unlocked
        else f"{gap_count} gap{'s' if gap_count != 1 else ''} under review"
    )
    return PerceptionGapsResponse(
        activity_status="available" if unlocked else "locked",
        dependency_message=(
            None if unlocked else PERCEPTION_GAPS_DEPENDENCY.locked_message
        ),
        progress=PerceptionGapProgress(
            gapCount=gap_count,
            evidenceSourceCount=source_count,
            requiredSourceCount=required_count,
            label=label,
        ),
        evidenceReferences=evidence_references,
        suggestedGaps=_suggested_gaps(state),
        gaps=state.output.perception_gaps,
        message=message,
    )


def _suggested_gaps(state: IdentifyState) -> list[PerceptionGap]:
    if state.output.perception_gaps:
        return []

    candidates = [
        item
        for item in state.evidence
        if item.source_activity != "perception-gaps"
    ]
    suggestions: list[PerceptionGap] = []
    evidence_by_id = {item.id: item for item in candidates}
    for finding in state.output.cross_check_findings:
        linked = [
            evidence_by_id[evidence_id]
            for evidence_id in finding.evidence_ids
            if evidence_id in evidence_by_id
        ]
        if len(linked) < 2:
            continue
        suggestions.append(
            PerceptionGap(
                topic=finding.topic.replace("_", " ").title(),
                perspectiveA=linked[0].claim,
                perspectiveB=linked[1].claim,
                difference=finding.explanation,
                supportingEvidenceIds=finding.evidence_ids,
                clarificationNeeded=True,
                resolution="unresolved",
            )
        )
        if len(suggestions) == 3:
            return suggestions
    return suggestions


def _evidence_references(state: IdentifyState) -> list[EvidenceReference]:
    references: list[EvidenceReference] = []
    references.extend(
        EvidenceReference(
            id=finding.id,
            sourceType="AI Detective",
            label=finding.topic,
            detail=finding.summary,
        )
        for finding in state.output.research_findings
    )
    references.extend(
        EvidenceReference(
            id=stakeholder.id,
            sourceType="Who Matters?",
            label=stakeholder.name,
            detail=stakeholder.insight or stakeholder.relationship,
        )
        for stakeholder in state.output.stakeholder_insights
    )
    if state.output.company_cards_evidence is not None:
        references.append(
            EvidenceReference(
                id=state.output.company_cards_evidence.id,
                sourceType="Company Cards",
                label="Today and future identity selections",
                detail=state.output.company_cards_evidence.explanation,
            )
        )
    references.extend(
        EvidenceReference(
            id=journey.id,
            sourceType="A Day in Their Shoes",
            label=journey.stakeholder_name,
            detail=f"{len(journey.touchpoints)} touchpoints",
        )
        for journey in state.output.stakeholder_journeys
    )
    if state.output.where_do_you_stand_evidence is not None:
        references.extend(
            EvidenceReference(
                id=response.id,
                sourceType="Where Do You Stand?",
                label=response.prompt,
                detail=response.response,
            )
            for response in state.output.where_do_you_stand_evidence.responses
        )
    references.extend(
        EvidenceReference(
            id=finding.id,
            sourceType="Signal Hunt",
            label=finding.signal,
            detail=finding.description,
        )
        for finding in state.output.pestle_findings
    )
    references.extend(
        EvidenceReference(
            id=evidence.id,
            sourceType=evidence.source.title,
            label=evidence.claim,
            detail=evidence.summary,
        )
        for evidence in state.evidence
    )
    return references


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
