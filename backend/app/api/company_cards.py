from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import CompanyCardSelectionState, CompanyCardsEvidence
from app.schemas.company_cards import (
    CompanyCardsProgress,
    CompanyCardsResponse,
    CompanyCardsUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["company-cards"])


@router.get(
    "/{session_id}/identify/company-cards",
    response_model=CompanyCardsResponse,
)
def get_company_cards(session_id: UUID) -> CompanyCardsResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state.output.company_cards_evidence)


@router.put(
    "/{session_id}/identify/company-cards",
    response_model=CompanyCardsResponse,
)
def update_company_cards(
    session_id: UUID, payload: CompanyCardsUpdateRequest
) -> CompanyCardsResponse:
    state = session_store.update_identify_company_cards(
        session_id=session_id,
        evidence=payload.to_evidence(),
    )
    if state is None:
        raise _session_not_found()

    return _response(
        state.output.company_cards_evidence,
        message="Company Cards selections saved as Identify evidence.",
    )


def _response(
    evidence: CompanyCardsEvidence | None,
    message: str | None = None,
) -> CompanyCardsResponse:
    current_count = 0
    desired_count = 0
    if evidence is not None:
        for selection in evidence.selections:
            if selection.state == CompanyCardSelectionState.current:
                current_count += 1
            if selection.state == CompanyCardSelectionState.desired:
                desired_count += 1

    label = (
        "No cards selected yet"
        if current_count == 0 and desired_count == 0
        else f"{current_count} today / {desired_count} future"
    )
    return CompanyCardsResponse(
        progress=CompanyCardsProgress(
            currentCount=current_count,
            desiredCount=desired_count,
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
