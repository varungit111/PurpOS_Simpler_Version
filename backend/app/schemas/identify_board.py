from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    IdentifyActivityState,
    OrganisationContext,
    PlaybookCoverage,
)


class IdentifyBoardConfidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    overall: int = Field(ge=0, le=100)
    sufficient_areas: int = Field(alias="sufficientAreas", ge=0)
    partial_areas: int = Field(alias="partialAreas", ge=0)
    total_areas: int = Field(alias="totalAreas", gt=0)


class IdentifyBoardStateResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    activity_id: str = Field(default="investigation-board")
    organisation: OrganisationContext
    activities: list[IdentifyActivityState] = Field(default_factory=list)
    playbook_coverage: list[PlaybookCoverage] = Field(
        default_factory=list,
        alias="playbookCoverage",
    )
    confidence: IdentifyBoardConfidence
