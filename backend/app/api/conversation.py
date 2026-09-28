from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.orchestrator.orchestrator import SessionNotFoundError, orchestrator
from app.schemas.conversation import ConversationAction
from app.schemas.conversation_api import (
    ActivityConversationRequest,
    ActivityConversationResponse,
)
from app.services.ai_client import (
    AIClient,
    AIProviderError,
    MissingAIAPIKeyError,
    create_ai_client,
)

router = APIRouter(prefix="/api/sessions", tags=["conversation"])


@router.post(
    "/{session_id}/conversation",
    response_model=ActivityConversationResponse,
)
def post_conversation(
    session_id: UUID, payload: ActivityConversationRequest
) -> ActivityConversationResponse:
    if payload.activity_id != "hot-seat":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only the Hot Seat activity is implemented.",
        )

    ai_client, ai_status = _get_ai_client()
    try:
        result = orchestrator.handle_activity_message(
            session_id=session_id,
            activity_id=payload.activity_id,
            content=payload.message,
            ai_client=ai_client,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        ) from exc

    conversation_result = result.conversation_result
    return ActivityConversationResponse(
        session_id=session_id,
        activity_id=payload.activity_id,
        assistant_message=_assistant_message(conversation_result.next_question),
        activity_status=result.activity_status,
        progress=result.progress,
        evidence_updates=result.evidence_updates,
        next_action=conversation_result.action,
        ai_status=ai_status,
    )


def _get_ai_client() -> tuple[AIClient | None, str]:
    try:
        return create_ai_client(), "connected"
    except MissingAIAPIKeyError:
        return None, "unavailable"
    except AIProviderError:
        return None, "unavailable"


def _assistant_message(next_question: str | None) -> str:
    if next_question:
        return next_question
    return "I've captured that for Hot Seat. Add anything else that feels important."
