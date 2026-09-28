from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import AlignmentState, DecisionCanvas, ProgressSnapshot, SuggestedMove


class AlignmentStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    alignment: AlignmentState


class DecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    question: str = Field(min_length=1)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    decision: DecisionCanvas


class SuggestedMovePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adopted: bool


class SuggestedMoveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    move: SuggestedMove


class ProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)
    snapshots: list[ProgressSnapshot]
