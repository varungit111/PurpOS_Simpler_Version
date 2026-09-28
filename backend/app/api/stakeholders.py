from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.stakeholders import (
    StakeholderMapResponse,
    StakeholderMapUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["stakeholders"])


@router.get(
    "/{session_id}/identify/stakeholders",
    response_model=StakeholderMapResponse,
)
def get_stakeholders(session_id: UUID) -> StakeholderMapResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        )

    return StakeholderMapResponse(stakeholders=state.output.stakeholder_insights)


@router.put(
    "/{session_id}/identify/stakeholders",
    response_model=StakeholderMapResponse,
)
def update_stakeholders(
    session_id: UUID, payload: StakeholderMapUpdateRequest
) -> StakeholderMapResponse:
    state = session_store.update_identify_stakeholders(
        session_id=session_id,
        stakeholders=payload.stakeholders,
    )
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        )

    return StakeholderMapResponse(stakeholders=state.output.stakeholder_insights)
