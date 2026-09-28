from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.assessment import PerceptionGap, PerceptionGapResolution


class EvidenceReference(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    source_type: str = Field(alias="sourceType")
    label: str
    detail: str | None = None


class PerceptionGapProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    gap_count: int = Field(alias="gapCount", ge=0)
    evidence_source_count: int = Field(alias="evidenceSourceCount", ge=0)
    required_source_count: int = Field(alias="requiredSourceCount", ge=1)
    label: str


class PerceptionGapsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="perception-gaps")
    activity_status: str
    dependency_message: str | None = None
    progress: PerceptionGapProgress
    evidence_references: list[EvidenceReference] = Field(
        default_factory=list,
        alias="evidenceReferences",
    )
    suggested_gaps: list[PerceptionGap] = Field(
        default_factory=list,
        alias="suggestedGaps",
    )
    gaps: list[PerceptionGap] = Field(default_factory=list)
    message: str | None = None


class PerceptionGapsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gaps: list[PerceptionGap] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_gap_evidence_links(self) -> "PerceptionGapsUpdateRequest":
        for gap in self.gaps:
            if not gap.supporting_evidence_ids:
                raise ValueError("Every perception gap must link supporting evidence.")
        return self


class PerceptionGapReviewRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    resolution: PerceptionGapResolution
    perspective_a: str | None = Field(default=None, alias="perspectiveA")
    perspective_b: str | None = Field(default=None, alias="perspectiveB")
    difference: str | None = None
    clarification_needed: bool | None = Field(
        default=None,
        alias="clarificationNeeded",
    )
    resolution_note: str | None = Field(default=None, alias="resolutionNote")
