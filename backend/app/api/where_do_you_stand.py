from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import (
    EvidenceSource,
    IdentifyEvidence,
    PositioningEvidenceTopic,
    WhereDoYouStandEvidence,
)
from app.schemas.where_do_you_stand import (
    WhereDoYouStandProgress,
    WhereDoYouStandResponse,
    WhereDoYouStandUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["where-do-you-stand"])


@router.get(
    "/{session_id}/identify/where-do-you-stand",
    response_model=WhereDoYouStandResponse,
)
def get_where_do_you_stand(session_id: UUID) -> WhereDoYouStandResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state.output.where_do_you_stand_evidence)


@router.put(
    "/{session_id}/identify/where-do-you-stand",
    response_model=WhereDoYouStandResponse,
)
def update_where_do_you_stand(
    session_id: UUID, payload: WhereDoYouStandUpdateRequest
) -> WhereDoYouStandResponse:
    evidence = payload.to_evidence()
    state = session_store.update_identify_where_do_you_stand(
        session_id=session_id,
        evidence=evidence,
        positioning_evidence=_positioning_evidence(evidence),
        social_contribution_evidence=_social_contribution_evidence(evidence),
    )
    if state is None:
        raise _session_not_found()

    return _response(
        state.output.where_do_you_stand_evidence,
        message="Where Do You Stand evidence saved for Define.",
    )


def _positioning_evidence(
    evidence: WhereDoYouStandEvidence,
) -> list[IdentifyEvidence]:
    return [
        _identify_evidence(response.prompt, response.response)
        for response in evidence.responses
        if response.topic != PositioningEvidenceTopic.social_contribution
    ]


def _social_contribution_evidence(
    evidence: WhereDoYouStandEvidence,
) -> list[IdentifyEvidence]:
    return [
        _identify_evidence(response.prompt, response.response)
        for response in evidence.responses
        if response.topic == PositioningEvidenceTopic.social_contribution
    ]


def _identify_evidence(claim: str, summary: str) -> IdentifyEvidence:
    return IdentifyEvidence(
        source=EvidenceSource(
            title="Where Do You Stand?",
            source_type="identify-activity",
        ),
        claim=claim,
        summary=summary,
    )


def _response(
    evidence: WhereDoYouStandEvidence | None,
    message: str | None = None,
) -> WhereDoYouStandResponse:
    response_count = len(evidence.responses) if evidence is not None else 0
    label = (
        "No evidence captured yet"
        if response_count == 0
        else f"{response_count} evidence response{'s' if response_count != 1 else ''}"
    )
    return WhereDoYouStandResponse(
        progress=WhereDoYouStandProgress(
            responseCount=response_count,
            label=label,
        ),
        evidence=evidence,
        message=message,
    )


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
