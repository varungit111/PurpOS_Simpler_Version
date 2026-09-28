from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.assessment import (
    PositioningEvidenceResponse,
    WhereDoYouStandEvidence,
)


class WhereDoYouStandProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    response_count: int = Field(alias="responseCount", ge=0)
    label: str


class WhereDoYouStandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="where-do-you-stand")
    progress: WhereDoYouStandProgress
    evidence: WhereDoYouStandEvidence | None = None
    message: str | None = None


class WhereDoYouStandUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    responses: list[PositioningEvidenceResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_responses(self) -> "WhereDoYouStandUpdateRequest":
        if not self.responses:
            raise ValueError("At least one evidence response is required.")
        return self

    def to_evidence(self) -> WhereDoYouStandEvidence:
        return WhereDoYouStandEvidence(responses=self.responses)
