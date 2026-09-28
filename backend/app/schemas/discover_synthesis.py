from pydantic import BaseModel, ConfigDict, Field


class DiscoverSynthesisProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    evidence_count: int = Field(alias="evidenceCount", ge=0)
    label: str


class DiscoverSynthesisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="discover-synthesis")
    statement: str | None = None
    gauge_items: list[str] = Field(default_factory=list)
    progress: DiscoverSynthesisProgress
    message: str | None = None


class DiscoverSynthesisUpdateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    statement: str = Field(min_length=1)
