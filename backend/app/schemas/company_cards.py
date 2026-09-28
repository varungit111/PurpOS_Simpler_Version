from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    CompanyCardSelection,
    CompanyCardSelectionState,
    CompanyCardsEvidence,
    NonEmptyString,
)


class CompanyCardsProgress(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    current_count: int = Field(alias="currentCount", ge=0)
    desired_count: int = Field(alias="desiredCount", ge=0)
    label: str


class CompanyCardsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(default="company-cards")
    content_status: str = Field(default="prototype-config")
    progress: CompanyCardsProgress
    evidence: CompanyCardsEvidence | None = None
    message: str | None = None


class CompanyCardsUpdateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    current_card_ids: list[NonEmptyString] = Field(
        default_factory=list,
        alias="currentCardIds",
    )
    desired_card_ids: list[NonEmptyString] = Field(
        default_factory=list,
        alias="desiredCardIds",
    )
    explanation: NonEmptyString | None = None

    def to_evidence(self) -> CompanyCardsEvidence:
        selections = [
            CompanyCardSelection(
                cardId=card_id,
                state=CompanyCardSelectionState.current,
            )
            for card_id in self.current_card_ids
        ]
        selections.extend(
            CompanyCardSelection(
                cardId=card_id,
                state=CompanyCardSelectionState.desired,
            )
            for card_id in self.desired_card_ids
        )
        return CompanyCardsEvidence(
            selections=selections,
            explanation=self.explanation,
        )
