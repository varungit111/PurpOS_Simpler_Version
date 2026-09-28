from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    DefineApprovalStatus,
    DefineState,
    PositioningStatement,
    ValueChainMoment,
    ValueChainMomentStatus,
    ValueCommitment,
    SingleOrganizingIdeaCandidate,
)


class SingleOrganizingIdeaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    statement: str | None = Field(default=None, min_length=1)
    guiding_star: str | None = Field(default=None, min_length=1, alias="guidingStar")
    meaning: str | None = Field(default=None, min_length=1)
    approval_status: DefineApprovalStatus = Field(default=DefineApprovalStatus.user_edited, alias="approvalStatus")


class SingleOrganizingIdeaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    soi: SingleOrganizingIdeaCandidate


class DefineStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    define: DefineState


class DefineGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    define: DefineState


class PositioningStatementPatch(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    audience: str | None = Field(default=None, min_length=1)
    category_context: str | None = Field(
        default=None,
        min_length=1,
        alias="categoryContext",
    )
    capability_value: str | None = Field(
        default=None,
        min_length=1,
        alias="capabilityValue",
    )
    reason_believability: str | None = Field(
        default=None,
        min_length=1,
        alias="reasonBelievability",
    )
    composed_statement: str | None = Field(
        default=None,
        min_length=1,
        alias="composedStatement",
    )
    evidence_ids: list[UUID] | None = Field(default=None, alias="evidenceIds")
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.user_edited,
        alias="approvalStatus",
    )


class PositioningStatementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positioning: PositioningStatement


class ValueCommitmentPatch(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    name: str | None = Field(default=None, min_length=1)
    meaning: str | None = Field(default=None, min_length=1)
    supporting_evidence: list[str] | None = Field(
        default=None,
        alias="supportingEvidence",
    )
    evidence_ids: list[UUID] | None = Field(default=None, alias="evidenceIds")
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.user_edited,
        alias="approvalStatus",
    )


class ValueCommitmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: ValueCommitment


class ValueChainMomentPatch(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    name: str | None = Field(default=None, min_length=1)
    question: str | None = Field(default=None, min_length=1)
    today: str | None = Field(default=None, min_length=1)
    desired_state: str | None = Field(
        default=None,
        min_length=1,
        alias="desiredState",
    )
    the_move: str | None = Field(default=None, min_length=1, alias="theMove")
    status: ValueChainMomentStatus | None = None
    supporting_evidence: list[str] | None = Field(
        default=None,
        alias="supportingEvidence",
    )
    evidence_ids: list[UUID] | None = Field(default=None, alias="evidenceIds")
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.user_edited,
        alias="approvalStatus",
    )


class ValueChainMomentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moment: ValueChainMoment
