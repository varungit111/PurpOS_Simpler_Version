from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import Stakeholder, StakeholderJourney


class StakeholderJourneyProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    journey_count: int = Field(alias="journeyCount", ge=0)
    stakeholder_count: int = Field(alias="stakeholderCount", ge=0)
    label: str


class StakeholderJourneyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="day-in-their-shoes")
    activity_status: str
    dependency_message: str | None = None
    progress: StakeholderJourneyProgress
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    journeys: list[StakeholderJourney] = Field(default_factory=list)
    message: str | None = None


class StakeholderJourneyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    journeys: list[StakeholderJourney] = Field(default_factory=list)
