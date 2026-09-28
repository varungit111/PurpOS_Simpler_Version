from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    AssessmentLifecycleStatus,
    AssessmentStage,
    IdentifyEvidence,
    utc_now,
)
from app.schemas.conversation import (
    ConversationContext,
    ConversationResult,
    StageConfig,
)


class StageHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_stage: AssessmentStage
    to_stage: AssessmentStage | None = None
    created_at: datetime = Field(default_factory=utc_now)
    note: str = Field(min_length=1)
    output_reference: str | None = None


class RevisitRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: AssessmentStage
    topic: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)


class AssessmentOrchestratorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    lifecycle_status: AssessmentLifecycleStatus = AssessmentLifecycleStatus.active
    current_stage: AssessmentStage
    next_stage: AssessmentStage | None = None
    stage_config: StageConfig
    context: ConversationContext
    handoffs: list[StageHandoff] = Field(default_factory=list)
    revisit_routes: list[RevisitRoute] = Field(default_factory=list)
    structured_outputs: dict[AssessmentStage, dict[str, Any]] = Field(
        default_factory=dict
    )
    updated_at: datetime = Field(default_factory=utc_now)


class OrchestratorMessageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: AssessmentOrchestratorState
    conversation_result: ConversationResult


class ActivityProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current: int = Field(ge=0)
    total: int = Field(gt=0)
    label: str = Field(min_length=1)


class ActivityConversationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: AssessmentOrchestratorState
    conversation_result: ConversationResult
    activity_id: str = Field(min_length=1)
    activity_status: str = Field(min_length=1)
    progress: ActivityProgress
    evidence_updates: list[IdentifyEvidence] = Field(default_factory=list)
