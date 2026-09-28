from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.orchestrator.orchestrator import SessionNotFoundError, StressTestBlockedError, StressTestCriterionNotFoundError, orchestrator
from app.schemas.stress_test import StressTestCriterionPatch, StressTestCriterionResponse, StressTestReviewPatch, StressTestStateResponse
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["stress-test"])


@router.get("/{session_id}/stress-test", response_model=StressTestStateResponse)
def get_stress_test(session_id: UUID):
    state = session_store.get_stress_test_state(session_id)
    if state is None: raise HTTPException(status_code=404, detail="Assessment session not found.")
    return StressTestStateResponse(stressTest=state)


@router.post("/{session_id}/stress-test/evaluate", response_model=StressTestStateResponse)
def evaluate(session_id: UUID):
    return StressTestStateResponse(stressTest=_call(lambda: orchestrator.evaluate_stress_test(session_id)))


@router.patch("/{session_id}/stress-test/criteria/{criterion_id}", response_model=StressTestCriterionResponse)
def update_criterion(session_id: UUID, criterion_id: str, payload: StressTestCriterionPatch):
    updates = payload.model_dump(exclude_unset=True, exclude={"approval_status"}, by_alias=False)
    try:
        state = orchestrator.update_stress_test_criterion(session_id, criterion_id, updates, approval_status=payload.approval_status)
    except StressTestCriterionNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (SessionNotFoundError, StressTestBlockedError) as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StressTestCriterionResponse(criterion=next(item for item in state.criteria if item.criterion_id == criterion_id))


@router.patch("/{session_id}/stress-test/review", response_model=StressTestStateResponse)
def update_review(session_id: UUID, payload: StressTestReviewPatch):
    return StressTestStateResponse(stressTest=_call(lambda: orchestrator.update_stress_test_review(session_id, payload.overarching_response)))


@router.post("/{session_id}/stress-test/complete", response_model=StressTestStateResponse)
def complete(session_id: UUID):
    return StressTestStateResponse(stressTest=_call(lambda: orchestrator.complete_stress_test(session_id)))


def _call(operation):
    try: return operation()
    except SessionNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StressTestBlockedError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
