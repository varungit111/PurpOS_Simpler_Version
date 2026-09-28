from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status

from app.orchestrator.orchestrator import (
    InvalidStageTransitionError,
    StageConfigNotFoundError,
    orchestrator,
)
from app.schemas.assessment import (
    AssessmentSession,
    AssessmentSessionCreate,
    IdentifyState,
    PlaybookCoverageStatus,
)
from app.schemas.identify_board import (
    IdentifyBoardConfidence,
    IdentifyBoardStateResponse,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=AssessmentSession,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: Annotated[AssessmentSessionCreate, Body()] = AssessmentSessionCreate(),
) -> AssessmentSession:
    try:
        state = orchestrator.start_assessment(payload=payload)
    except (InvalidStageTransitionError, StageConfigNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The requested assessment stage is not implemented.",
        ) from exc
    session = session_store.get(state.session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assessment session could not be loaded after creation.",
        )
    return session


@router.get("/{session_id}", response_model=AssessmentSession)
def get_session(session_id: UUID) -> AssessmentSession:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        )
    return session


@router.get("/{session_id}/state", response_model=IdentifyState)
def get_session_state(session_id: UUID) -> IdentifyState:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        )
    return state


@router.get(
    "/{session_id}/identify/board",
    response_model=IdentifyBoardStateResponse,
)
def get_identify_board_state(session_id: UUID) -> IdentifyBoardStateResponse:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        )

    coverage = session.identify.playbook_coverage
    sufficient_count = sum(
        1 for item in coverage if item.status == PlaybookCoverageStatus.sufficient
    )
    partial_count = sum(
        1 for item in coverage if item.status == PlaybookCoverageStatus.partial
    )
    total = max(len(coverage), 1)
    overall = round(((sufficient_count + partial_count * 0.5) / total) * 100)

    return IdentifyBoardStateResponse(
        organisation=session.organisation,
        activities=list(session.identify.activity_states.values()),
        playbookCoverage=coverage,
        confidence=IdentifyBoardConfidence(
            overall=overall,
            sufficientAreas=sufficient_count,
            partialAreas=partial_count,
            totalAreas=total,
        ),
    )
