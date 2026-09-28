from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import ExternalResearchState, ResearchFinding


class AIDetectiveProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    findings_count: int = Field(alias="findingsCount", ge=0)
    label: str
    limitation: str | None = None


class AIDetectiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="ai-detective")
    research_status: str = Field(default="idle")
    progress: AIDetectiveProgress
    findings: list[ResearchFinding] = Field(default_factory=list)
    external_research: ExternalResearchState = Field(alias="externalResearch")
    message: str | None = None


class AIDetectiveUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ResearchFinding] = Field(default_factory=list)


class AIDetectiveGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ResearchFinding] = Field(default_factory=list)
