from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import IdentifyState
from app.schemas.discover_synthesis import (
    DiscoverSynthesisProgress,
    DiscoverSynthesisResponse,
    DiscoverSynthesisUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["discover-synthesis"])


@router.get(
    "/{session_id}/identify/discover-synthesis",
    response_model=DiscoverSynthesisResponse,
)
def get_discover_synthesis(session_id: UUID) -> DiscoverSynthesisResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state.output.discovery_brief, _gauge_items(state))


@router.post(
    "/{session_id}/identify/discover-synthesis/generate",
    response_model=DiscoverSynthesisResponse,
)
def generate_discover_synthesis(session_id: UUID) -> DiscoverSynthesisResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    statement = _generate_statement(state)
    if statement is None:
        return _response(
            state.output.discovery_brief,
            _gauge_items(state),
            message="Complete AI Detective or Signal Hunt before synthesis.",
        )

    updated = session_store.update_identify_discovery_brief(
        session_id=session_id,
        discovery_brief=statement,
    )
    if updated is None:
        raise _session_not_found()
    return _response(
        updated.output.discovery_brief,
        _gauge_items(updated),
        message="Discover synthesis generated from reviewed evidence.",
    )


@router.put(
    "/{session_id}/identify/discover-synthesis",
    response_model=DiscoverSynthesisResponse,
)
def update_discover_synthesis(
    session_id: UUID,
    payload: DiscoverSynthesisUpdateRequest,
) -> DiscoverSynthesisResponse:
    updated = session_store.update_identify_discovery_brief(
        session_id=session_id,
        discovery_brief=payload.statement,
    )
    if updated is None:
        raise _session_not_found()
    return _response(
        updated.output.discovery_brief,
        _gauge_items(updated),
        message="Discover synthesis saved.",
    )


def _generate_statement(state: IdentifyState) -> str | None:
    accepted_findings = [
        finding
        for finding in state.output.research_findings
        if finding.classification in {"correct", "interesting"}
    ]
    placed_signals = [
        finding
        for finding in state.output.pestle_findings
        if finding.decision in {"watch", "opportunity", "threat"}
    ]
    if not accepted_findings and not placed_signals:
        return None

    evidence_points = [
        finding.summary for finding in accepted_findings[:3]
    ] + [
        f"{finding.signal}: {finding.why_it_matters}"
        for finding in placed_signals[:2]
    ]
    return " ".join(evidence_points)


def _gauge_items(state: IdentifyState) -> list[str]:
    items: list[str] = []
    items.extend(
        f"{finding.topic}: {finding.classification.value}"
        for finding in state.output.research_findings
    )
    items.extend(
        f"{finding.signal}: {finding.decision.value}"
        for finding in state.output.pestle_findings
        if finding.decision != "unplaced"
    )
    return items


def _response(
    statement: str | None,
    gauge_items: list[str],
    message: str | None = None,
) -> DiscoverSynthesisResponse:
    evidence_count = len(gauge_items)
    label = (
        "No Discover evidence synthesized yet"
        if evidence_count == 0
        else f"{evidence_count} Discover evidence items"
    )
    return DiscoverSynthesisResponse(
        statement=statement,
        gauge_items=gauge_items,
        progress=DiscoverSynthesisProgress(
            evidenceCount=evidence_count,
            label=label,
        ),
        message=message,
    )


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
