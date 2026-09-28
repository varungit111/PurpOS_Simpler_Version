from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import IdentifyEvidence
from app.schemas.conversation import ConversationAction
from app.schemas.orchestrator import ActivityProgress


class ActivityConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    activity_id: str = Field(min_length=1)


class ActivityConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    activity_id: str
    assistant_message: str
    activity_status: str
    progress: ActivityProgress
    evidence_updates: list[IdentifyEvidence]
    next_action: ConversationAction
    ai_status: str
