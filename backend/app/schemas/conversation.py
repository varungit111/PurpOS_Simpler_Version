from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    AssessmentStage,
    IdentifyEvidence,
    PlaybookCoverageStatus,
    utc_now,
)


class ConversationRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ConversationAction(StrEnum):
    ask_question = "ask_question"
    revisit_topic = "revisit_topic"
    retrieve_evidence = "retrieve_evidence"
    validate_output = "validate_output"
    continue_stage = "continue_stage"


class CrossCheckIssueType(StrEnum):
    gap = "gap"
    vagueness = "vagueness"
    contradiction = "contradiction"


class CompletionCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    enabled: bool = True


class CrossCheckTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    fields: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class QuestionEvidenceArea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    question: str = Field(min_length=1)
    evidence_prompt: str = Field(min_length=1)
    structured_field: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)


class StageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: AssessmentStage
    system_instructions: str = Field(min_length=1)
    question_requirements: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    required_structured_fields: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    output_schema: str = Field(min_length=1)
    completion_criteria: list[CompletionCriterion] = Field(default_factory=list)
    cross_check_targets: list[CrossCheckTarget] = Field(default_factory=list)
    question_evidence_areas: list[QuestionEvidenceArea] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    role: ConversationRole
    content: str = Field(min_length=1)
    evidence: list[IdentifyEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class CrossCheckFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: CrossCheckIssueType
    target: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    source_activities: list[str] = Field(default_factory=list)


class ConversationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: AssessmentStage
    turns: list[ConversationTurn] = Field(default_factory=list)
    collected_fields: dict[str, str] = Field(default_factory=dict)
    covered_question_area_ids: list[str] = Field(default_factory=list)
    question_area_statuses: dict[str, PlaybookCoverageStatus] = Field(
        default_factory=dict
    )
    identify_evidence_context: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[IdentifyEvidence] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    cross_check_findings: list[CrossCheckFinding] = Field(default_factory=list)
    retrieved_evidence: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class StructuredEvidenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_required: bool = False
    coverage_area_ids: list[str] = Field(default_factory=list)


class AIConversationRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_action: ConversationAction
    next_question: str | None = Field(default=None, min_length=1)
    revisit_target: str | None = Field(default=None, min_length=1)
    structured_updates: list[StructuredEvidenceUpdate] = Field(default_factory=list)
    rationale: str | None = Field(default=None, min_length=1)


class ConversationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ConversationContext
    action: ConversationAction
    next_question: str | None = None
    revisit_target: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    output_valid: bool = False
    output_errors: list[str] = Field(default_factory=list)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    structured_evidence_updates: list[StructuredEvidenceUpdate] = Field(
        default_factory=list
    )
