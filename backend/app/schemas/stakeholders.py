from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import Stakeholder


class StakeholderMapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="who-matters")
    stakeholders: list[Stakeholder] = Field(default_factory=list)


class StakeholderMapUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stakeholders: list[Stakeholder] = Field(default_factory=list)
