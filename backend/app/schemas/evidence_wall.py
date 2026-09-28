from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import IdentifyTheme, PlaybookCoverageStatus


class EvidenceWallCard(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    source_activity: str | None = Field(alias="sourceActivity")
    source_label: str = Field(alias="sourceLabel")
    claim: str
    summary: str | None = None
    card_type: str = Field(alias="cardType")
    coverage_area_ids: list[str] = Field(
        default_factory=list,
        alias="coverageAreaIds",
    )
    evidence_status: str = Field(alias="evidenceStatus")
    source_reference: str | None = Field(default=None, alias="sourceReference")
    derived_from_evidence_ids: list[UUID] = Field(
        default_factory=list,
        alias="derivedFromEvidenceIds",
    )


class EvidenceWallCoverageArea(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    area_id: str = Field(alias="areaId")
    label: str
    question: str
    status: PlaybookCoverageStatus
    evidence_count: int = Field(alias="evidenceCount", ge=0)


class EvidenceWallGroup(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: str
    title: str
    status: PlaybookCoverageStatus
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    cards: list[EvidenceWallCard] = Field(default_factory=list)


class EvidenceWallResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    activity_id: str = Field(default="evidence-wall", alias="activity_id")
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    coverage_areas: list[EvidenceWallCoverageArea] = Field(
        default_factory=list,
        alias="coverageAreas",
    )
    groups: list[EvidenceWallGroup] = Field(default_factory=list)
    selected_themes: list[IdentifyTheme] = Field(
        default_factory=list,
        alias="selectedThemes",
    )
    message: str | None = None


class EvidenceWallUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_group_ids: list[str] = Field(
        default_factory=list,
        alias="selectedGroupIds",
    )
