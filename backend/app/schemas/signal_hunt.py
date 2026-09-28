from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import PESTLECategory, PESTLEFinding


class SignalHuntProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    findings_count: int = Field(alias="findingsCount", ge=0)
    categories_covered: list[PESTLECategory] = Field(
        default_factory=list,
        alias="categoriesCovered",
    )
    total_categories: int = Field(default=6, alias="totalCategories")
    label: str


class SignalHuntResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="signal-hunt")
    ai_status: str = Field(default="idle")
    progress: SignalHuntProgress
    findings: list[PESTLEFinding] = Field(default_factory=list)
    message: str | None = None


class SignalHuntUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[PESTLEFinding] = Field(default_factory=list)


class SignalHuntGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[PESTLEFinding] = Field(default_factory=list)
