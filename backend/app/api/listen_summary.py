from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import AssessmentSession, IdentifyEvidence
from app.schemas.listen_summary import (
    ListenSummaryArea,
    ListenSummaryQuote,
    ListenSummaryResponse,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["listen-summary"])

LISTEN_ACTIVITY_IDS = {"who-matters", "hot-seat", "company-cards"}


@router.get(
    "/{session_id}/identify/listen-summary",
    response_model=ListenSummaryResponse,
)
def get_listen_summary(session_id: UUID) -> ListenSummaryResponse:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment session not found.",
        )

    return build_listen_summary(session)


def build_listen_summary(session: AssessmentSession) -> ListenSummaryResponse:
    listen_evidence = [
        item
        for item in session.identify.evidence
        if item.source_activity in LISTEN_ACTIVITY_IDS
    ]
    listen_evidence_ids = {item.id for item in listen_evidence}
    company_cards_count = 0
    if session.identify.output.company_cards_evidence is not None:
        company_cards_count = len(
            session.identify.output.company_cards_evidence.selections
        )

    return ListenSummaryResponse(
        evidenceCount=len(listen_evidence),
        stakeholderCount=len(session.identify.output.stakeholder_insights),
        hotSeatEvidenceCount=len(
            [
                item
                for item in listen_evidence
                if item.source_activity == "hot-seat"
            ]
        ),
        companyCardsCount=company_cards_count,
        areasMoved=_areas_moved(session, listen_evidence_ids),
        quotes=_quotes(listen_evidence),
        tension=_tension(session),
        message=(
            None
            if listen_evidence
            else "Complete Who Matters, Hot Seat or Company Cards to create a Listen summary."
        ),
    )


def _areas_moved(
    session: AssessmentSession,
    listen_evidence_ids: set[UUID],
) -> list[ListenSummaryArea]:
    areas: list[ListenSummaryArea] = []
    for coverage in session.identify.playbook_coverage:
        evidence_count = len(
            [
                evidence_id
                for evidence_id in coverage.evidence_ids
                if evidence_id in listen_evidence_ids
            ]
        )
        if evidence_count == 0:
            continue
        areas.append(
            ListenSummaryArea(
                areaId=coverage.area_id,
                label=coverage.label,
                status=coverage.status.value,
                evidenceCount=evidence_count,
                note=f"{evidence_count} Listen evidence item{'s' if evidence_count != 1 else ''}",
            )
        )
    return sorted(areas, key=lambda area: area.evidence_count, reverse=True)[:6]


def _quotes(evidence: list[IdentifyEvidence]) -> list[ListenSummaryQuote]:
    return [
        ListenSummaryQuote(
            id=str(item.id),
            sourceActivity=item.source_activity or "listen",
            text=item.claim,
        )
        for item in evidence[:8]
    ]


def _tension(session: AssessmentSession) -> str | None:
    if session.identify.output.vulnerabilities_gaps:
        return session.identify.output.vulnerabilities_gaps[0]
    if session.identify.output.open_questions:
        return f"Still unclear: {session.identify.output.open_questions[0]}"
    if (
        session.identify.output.stakeholder_insights
        and session.identify.output.company_cards_evidence is None
    ):
        return "You have named who matters, but not yet tested the organisation's self-image with Company Cards."
    return None
