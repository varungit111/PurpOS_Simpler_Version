from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.assessment import DefineApprovalStatus, StressTestCriterionResult, StressTestCriterionStatus, StressTestState


class StressTestStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    stress_test: StressTestState = Field(alias="stressTest")


class StressTestCriterionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    status: StressTestCriterionStatus | None = None
    reasoning: str | None = Field(default=None, min_length=1)
    supporting_evidence_ids: list[UUID] | None = Field(default=None, alias="supportingEvidenceIds")
    concerns: list[str] | None = None
    suggested_refinement: str | None = Field(default=None, min_length=1, alias="suggestedRefinement")
    approval_status: DefineApprovalStatus = Field(default=DefineApprovalStatus.user_edited, alias="approvalStatus")


class StressTestCriterionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: StressTestCriterionResult


class StressTestReviewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    overarching_response: str = Field(min_length=1, alias="overarchingResponse")
