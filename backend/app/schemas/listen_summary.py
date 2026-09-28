from pydantic import BaseModel, ConfigDict, Field


class ListenSummaryArea(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    area_id: str = Field(alias="areaId", min_length=1)
    label: str = Field(min_length=1)
    status: str = Field(min_length=1)
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    note: str = Field(min_length=1)


class ListenSummaryQuote(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: str = Field(min_length=1)
    source_activity: str = Field(alias="sourceActivity", min_length=1)
    text: str = Field(min_length=1)


class ListenSummaryResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    activity_id: str = Field(default="listen-summary")
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    stakeholder_count: int = Field(alias="stakeholderCount", ge=0)
    hot_seat_evidence_count: int = Field(alias="hotSeatEvidenceCount", ge=0)
    company_cards_count: int = Field(alias="companyCardsCount", ge=0)
    areas_moved: list[ListenSummaryArea] = Field(
        default_factory=list,
        alias="areasMoved",
    )
    quotes: list[ListenSummaryQuote] = Field(default_factory=list)
    tension: str | None = None
    message: str | None = None
