from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import PlaybookCoverageStatus


class IdentifyBriefTheme(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    name: str
    summary: str
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    is_lead: bool = Field(default=False, alias="isLead")


class IdentifyBriefEvidence(BaseModel):
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


class IdentifyBriefQuestion(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: str
    question: str
    source: str
    supporting_evidence_ids: list[UUID] = Field(
        default_factory=list,
        alias="supportingEvidenceIds",
    )


class IdentifyBriefCoverageArea(BaseModel):
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


class IdentifyBriefSourceBreakdown(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    discover: int = Field(ge=0)
    listen: int = Field(ge=0)
    understand: int = Field(ge=0)


class IdentifyBriefReadiness(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    is_ready: bool = Field(alias="isReady")
    covered_area_count: int = Field(alias="coveredAreaCount", ge=0)
    total_area_count: int = Field(alias="totalAreaCount", ge=1)
    required_evidence_sources: list[str] = Field(
        default_factory=list,
        alias="requiredEvidenceSources",
    )
    missing: list[str] = Field(default_factory=list)


class IdentifyBriefResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    activity_id: str = Field(default="identify-brief", alias="activity_id")
    organisation_name: str = Field(alias="organisationName")
    website: str | None = None
    statement: str
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    source_breakdown: IdentifyBriefSourceBreakdown = Field(alias="sourceBreakdown")
    themes: list[IdentifyBriefTheme] = Field(default_factory=list)
    strongest_evidence: list[IdentifyBriefEvidence] = Field(
        default_factory=list,
        alias="strongestEvidence",
    )
    open_questions: list[IdentifyBriefQuestion] = Field(
        default_factory=list,
        alias="openQuestions",
    )
    coverage: list[IdentifyBriefCoverageArea] = Field(default_factory=list)
    unresolved_gap_count: int = Field(alias="unresolvedGapCount", ge=0)
    readiness: IdentifyBriefReadiness
    handoff_label: str = Field(alias="handoffLabel")
