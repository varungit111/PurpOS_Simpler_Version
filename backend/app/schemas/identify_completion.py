from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    AssessmentStage,
    IdentifyCompletionStatus,
    IdentifyOutput,
    PlaybookCoverage,
)
from app.schemas.identify_brief import IdentifyBriefResponse


class IdentifyCompletionIssue(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    activity_id: str | None = Field(default=None, alias="activityId")
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")


class IdentifyCompletionReadiness(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    status: IdentifyCompletionStatus
    can_complete: bool = Field(alias="canComplete")
    blocking_issues: list[IdentifyCompletionIssue] = Field(
        default_factory=list,
        alias="blockingIssues",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        alias="openQuestions",
    )


class IdentifyHandoffRevisit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime


class IdentifyHandoff(BaseModel):
    """Canonical, evidence-linked snapshot passed from Identify to Define."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    assessment_id: UUID = Field(alias="assessmentId")
    from_stage: AssessmentStage = Field(default=AssessmentStage.identify, alias="fromStage")
    to_stage: AssessmentStage = Field(default=AssessmentStage.define, alias="toStage")
    completion_status: IdentifyCompletionStatus = Field(alias="completionStatus")
    completed_at: datetime = Field(alias="completedAt")
    output: IdentifyOutput
    brief: IdentifyBriefResponse
    coverage: list[PlaybookCoverage] = Field(default_factory=list)
    strongest_evidence_ids: list[UUID] = Field(
        default_factory=list,
        alias="strongestEvidenceIds",
    )
    evidence_references: list[UUID] = Field(
        default_factory=list,
        alias="evidenceReferences",
    )
    open_questions: list[str] = Field(default_factory=list, alias="openQuestions")
    revisit_history: list[IdentifyHandoffRevisit] = Field(
        default_factory=list,
        alias="revisitHistory",
    )


class IdentifyCompletionResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    readiness: IdentifyCompletionReadiness
    handoff: IdentifyHandoff | None = None
