from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.orchestrator.orchestrator import (
    DefineEntryBlockedError,
    DefineCompletionBlockedError,
    DefineItemNotFoundError,
    SessionNotFoundError,
    orchestrator,
)
from app.schemas.define import (
    DefineGenerateResponse,
    DefineStateResponse,
    PositioningStatementPatch,
    PositioningStatementResponse,
    ValueChainMomentPatch,
    ValueChainMomentResponse,
    ValueCommitmentPatch,
    ValueCommitmentResponse,
    SingleOrganizingIdeaPatch,
    SingleOrganizingIdeaResponse,
)
from app.schemas.define_completion import DefineCompletionResponse
from app.services.define_readiness import evaluate_define_readiness
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["define"])


@router.get("/{session_id}/define", response_model=DefineStateResponse)
def get_define(session_id: UUID) -> DefineStateResponse:
    define = session_store.get_define_state(session_id)
    if define is None:
        raise _session_not_found()
    return DefineStateResponse(define=define)


@router.post(
    "/{session_id}/define/generate",
    response_model=DefineGenerateResponse,
)
def generate_define(session_id: UUID) -> DefineGenerateResponse:
    try:
        define = orchestrator.initialize_define(session_id)
    except SessionNotFoundError as exc:
        raise _session_not_found() from exc
    except DefineEntryBlockedError as exc:
        raise _define_blocked(str(exc)) from exc
    return DefineGenerateResponse(define=define)


@router.get("/{session_id}/define/completion", response_model=DefineCompletionResponse)
def get_define_completion(session_id: UUID) -> DefineCompletionResponse:
    session = session_store.get(session_id)
    if session is None: raise _session_not_found()
    return DefineCompletionResponse(readiness=evaluate_define_readiness(session), output=session.define.output if session.define.status == "completed" else None)


@router.post("/{session_id}/define/complete", response_model=DefineCompletionResponse)
def complete_define(session_id: UUID) -> DefineCompletionResponse:
    try:
        readiness, output = orchestrator.complete_define(session_id)
    except SessionNotFoundError as exc: raise _session_not_found() from exc
    except DefineCompletionBlockedError as exc:
        raise HTTPException(status_code=409, detail=exc.readiness.model_dump(mode="json", by_alias=True)) from exc
    except DefineEntryBlockedError as exc: raise _define_blocked(str(exc)) from exc
    return DefineCompletionResponse(readiness=readiness, output=output)


@router.patch("/{session_id}/define/soi", response_model=SingleOrganizingIdeaResponse)
def update_define_soi(session_id: UUID, payload: SingleOrganizingIdeaPatch) -> SingleOrganizingIdeaResponse:
    updates = payload.model_dump(exclude_unset=True, exclude={"approval_status"}, by_alias=False)
    try:
        define = orchestrator.update_define_soi(session_id, updates, approval_status=payload.approval_status)
    except SessionNotFoundError as exc: raise _session_not_found() from exc
    except DefineItemNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DefineEntryBlockedError as exc: raise _define_blocked(str(exc)) from exc
    assert define.soi_candidate is not None
    return SingleOrganizingIdeaResponse(soi=define.soi_candidate)


@router.patch(
    "/{session_id}/define/positioning",
    response_model=PositioningStatementResponse,
)
def update_define_positioning(
    session_id: UUID,
    payload: PositioningStatementPatch,
) -> PositioningStatementResponse:
    updates = payload.model_dump(
        exclude_unset=True,
        exclude={"approval_status"},
        by_alias=False,
    )
    try:
        define = orchestrator.update_define_positioning(
            session_id,
            updates,
            approval_status=payload.approval_status,
        )
    except SessionNotFoundError as exc:
        raise _session_not_found() from exc
    except DefineEntryBlockedError as exc:
        raise _define_blocked(str(exc)) from exc
    return PositioningStatementResponse(positioning=define.positioning)


@router.patch(
    "/{session_id}/define/values/{value_id}",
    response_model=ValueCommitmentResponse,
)
def update_define_value(
    session_id: UUID,
    value_id: UUID,
    payload: ValueCommitmentPatch,
) -> ValueCommitmentResponse:
    updates = payload.model_dump(
        exclude_unset=True,
        exclude={"approval_status"},
        by_alias=False,
    )
    try:
        define = orchestrator.update_define_value(
            session_id,
            value_id,
            updates,
            approval_status=payload.approval_status,
        )
    except SessionNotFoundError as exc:
        raise _session_not_found() from exc
    except DefineItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DefineEntryBlockedError as exc:
        raise _define_blocked(str(exc)) from exc
    value = next(item for item in define.values if item.id == value_id)
    return ValueCommitmentResponse(value=value)


@router.patch(
    "/{session_id}/define/moments/{moment_id}",
    response_model=ValueChainMomentResponse,
)
def update_define_moment(
    session_id: UUID,
    moment_id: UUID,
    payload: ValueChainMomentPatch,
) -> ValueChainMomentResponse:
    updates = payload.model_dump(
        exclude_unset=True,
        exclude={"approval_status"},
        by_alias=False,
    )
    try:
        define = orchestrator.update_define_moment(
            session_id,
            moment_id,
            updates,
            approval_status=payload.approval_status,
        )
    except SessionNotFoundError as exc:
        raise _session_not_found() from exc
    except DefineItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DefineEntryBlockedError as exc:
        raise _define_blocked(str(exc)) from exc
    moment = next(item for item in define.moments if item.id == moment_id)
    return ValueChainMomentResponse(moment=moment)


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )


def _define_blocked(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )
