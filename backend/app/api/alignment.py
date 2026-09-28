from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.orchestrator.orchestrator import (
    AlignmentBlockedError,
    AlignmentItemNotFoundError,
    SessionNotFoundError,
    orchestrator,
)
from app.schemas.alignment import (
    AlignmentStateResponse,
    DecisionCreate,
    DecisionResponse,
    ProgressResponse,
    SuggestedMovePatch,
    SuggestedMoveResponse,
)
from app.store.sessions import session_store


router = APIRouter(prefix="/api/sessions", tags=["alignment"])


@router.get("/{session_id}/align", response_model=AlignmentStateResponse)
def get_alignment(session_id: UUID) -> AlignmentStateResponse:
    state = session_store.get_alignment_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Assessment session not found.")
    return AlignmentStateResponse(alignment=state)


@router.post("/{session_id}/align/generate", response_model=AlignmentStateResponse)
def generate_alignment(session_id: UUID) -> AlignmentStateResponse:
    return AlignmentStateResponse(alignment=_call(lambda: orchestrator.initialize_alignment(session_id)))


@router.post(
    "/{session_id}/align/decisions",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(session_id: UUID, payload: DecisionCreate) -> DecisionResponse:
    return DecisionResponse(
        decision=_call(lambda: orchestrator.create_alignment_decision(session_id, payload.question))
    )


@router.post("/{session_id}/align/decisions/{decision_id}/reframe", response_model=DecisionResponse)
def reframe_decision(session_id: UUID, decision_id: UUID) -> DecisionResponse:
    return DecisionResponse(
        decision=_call(lambda: orchestrator.reframe_alignment_decision(session_id, decision_id))
    )


@router.post("/{session_id}/align/decisions/{decision_id}/evaluate", response_model=DecisionResponse)
def evaluate_decision(session_id: UUID, decision_id: UUID) -> DecisionResponse:
    return DecisionResponse(
        decision=_call(lambda: orchestrator.evaluate_alignment_decision(session_id, decision_id))
    )


@router.patch("/{session_id}/align/moves/{move_id}", response_model=SuggestedMoveResponse)
def update_move(session_id: UUID, move_id: UUID, payload: SuggestedMovePatch) -> SuggestedMoveResponse:
    return SuggestedMoveResponse(
        move=_call(lambda: orchestrator.update_alignment_move(session_id, move_id, payload.adopted))
    )


@router.get("/{session_id}/align/progress", response_model=ProgressResponse)
def get_progress(session_id: UUID) -> ProgressResponse:
    state = session_store.get_alignment_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Assessment session not found.")
    return ProgressResponse(snapshots=state.progress_snapshots)


def _call(operation):
    try:
        return operation()
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlignmentItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (AlignmentBlockedError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
