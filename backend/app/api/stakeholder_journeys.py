from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.config.identify_dependencies import DAY_IN_THEIR_SHOES_DEPENDENCY
from app.schemas.assessment import IdentifyState, StakeholderJourney
from app.schemas.stakeholder_journeys import (
    StakeholderJourneyProgress,
    StakeholderJourneyResponse,
    StakeholderJourneyUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["stakeholder-journeys"])


@router.get(
    "/{session_id}/identify/stakeholder-journeys",
    response_model=StakeholderJourneyResponse,
)
def get_stakeholder_journeys(session_id: UUID) -> StakeholderJourneyResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state)


@router.put(
    "/{session_id}/identify/stakeholder-journeys",
    response_model=StakeholderJourneyResponse,
)
def update_stakeholder_journeys(
    session_id: UUID, payload: StakeholderJourneyUpdateRequest
) -> StakeholderJourneyResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()
    if not DAY_IN_THEIR_SHOES_DEPENDENCY.is_satisfied(state):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=DAY_IN_THEIR_SHOES_DEPENDENCY.locked_message,
        )

    _validate_journey_stakeholders(state, payload.journeys)
    updated = session_store.update_identify_stakeholder_journeys(
        session_id=session_id,
        journeys=payload.journeys,
    )
    if updated is None:
        raise _session_not_found()

    return _response(
        updated,
        message="Stakeholder journeys saved as Identify evidence.",
    )


def _validate_journey_stakeholders(
    state: IdentifyState,
    journeys: list[StakeholderJourney],
) -> None:
    stakeholder_ids = {
        stakeholder.id for stakeholder in state.output.stakeholder_insights
    }
    unknown_ids = [
        journey.stakeholder_id
        for journey in journeys
        if journey.stakeholder_id not in stakeholder_ids
    ]
    if unknown_ids:
        raise HTTPException(
            status_code=422,
            detail="Each journey must reference a stakeholder from Who Matters?.",
        )


def _response(
    state: IdentifyState,
    message: str | None = None,
) -> StakeholderJourneyResponse:
    unlocked = DAY_IN_THEIR_SHOES_DEPENDENCY.is_satisfied(state)
    journey_count = len(state.output.stakeholder_journeys)
    stakeholder_count = len(state.output.stakeholder_insights)
    label = (
        "Locked"
        if not unlocked
        else f"{journey_count} journey{'s' if journey_count != 1 else ''} mapped"
    )
    return StakeholderJourneyResponse(
        activity_status="available" if unlocked else "locked",
        dependency_message=(
            None if unlocked else DAY_IN_THEIR_SHOES_DEPENDENCY.locked_message
        ),
        progress=StakeholderJourneyProgress(
            journeyCount=journey_count,
            stakeholderCount=stakeholder_count,
            label=label,
        ),
        stakeholders=state.output.stakeholder_insights,
        journeys=state.output.stakeholder_journeys,
        message=message,
    )


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
