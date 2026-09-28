from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import DefineOutput, DefineStatus


class DefineCompletionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")


class DefineCompletionReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    status: DefineStatus
    can_complete: bool = Field(alias="canComplete")
    blocking_issues: list[DefineCompletionIssue] = Field(default_factory=list, alias="blockingIssues")
    open_questions: list[str] = Field(default_factory=list, alias="openQuestions")


class DefineCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    readiness: DefineCompletionReadiness
    output: DefineOutput | None = None
