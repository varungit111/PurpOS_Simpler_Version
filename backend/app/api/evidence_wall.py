from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import IdentifyEvidence, IdentifyState, IdentifyTheme
from app.schemas.evidence_wall import (
    EvidenceWallCard,
    EvidenceWallCoverageArea,
    EvidenceWallGroup,
    EvidenceWallResponse,
    EvidenceWallUpdateRequest,
)
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["evidence-wall"])

SOURCE_LABELS = {
    "ai-detective": "AI Detective",
    "signal-hunt": "Signal Hunt",
    "discover-synthesis": "Discover Synthesis",
    "who-matters": "Who Matters?",
    "hot-seat": "Hot Seat",
    "company-cards": "Company Cards",
    "listen-summary": "Listen Summary",
    "day-in-their-shoes": "A Day in Their Shoes",
    "where-do-you-stand": "Where Do You Stand?",
    "perception-gaps": "Perception Gaps",
    "cross-check": "Cross-check",
}


@router.get(
    "/{session_id}/identify/evidence-wall",
    response_model=EvidenceWallResponse,
)
def get_evidence_wall(session_id: UUID) -> EvidenceWallResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state)


@router.put(
    "/{session_id}/identify/evidence-wall",
    response_model=EvidenceWallResponse,
)
def update_evidence_wall(
    session_id: UUID,
    payload: EvidenceWallUpdateRequest,
) -> EvidenceWallResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    groups = _groups(state)
    group_by_id = {group.id: group for group in groups}
    unknown_ids = [
        group_id
        for group_id in payload.selected_group_ids
        if group_id not in group_by_id
    ]
    if unknown_ids:
        raise HTTPException(
            status_code=422,
            detail="Every selected Evidence Wall group must exist.",
        )

    themes = [
        IdentifyTheme(
            name=group_by_id[group_id].title,
            summary=(
                f"{group_by_id[group_id].evidence_count} evidence item"
                f"{'s' if group_by_id[group_id].evidence_count != 1 else ''} "
                "clustered on the Evidence Wall."
            ),
            evidence_ids=[card.id for card in group_by_id[group_id].cards],
        )
        for group_id in payload.selected_group_ids
    ]

    updated = session_store.update_identify_themes(
        session_id=session_id,
        themes=themes,
    )
    if updated is None:
        raise _session_not_found()

    return _response(updated, message="Evidence Wall synthesis saved.")


def _response(
    state: IdentifyState,
    message: str | None = None,
) -> EvidenceWallResponse:
    return EvidenceWallResponse(
        evidenceCount=len(state.evidence),
        coverageAreas=[
            EvidenceWallCoverageArea(
                areaId=area.area_id,
                label=area.label,
                question=area.question,
                status=area.status,
                evidenceCount=len(area.evidence_ids),
            )
            for area in state.playbook_coverage
        ],
        groups=_groups(state),
        selectedThemes=state.output.themes,
        message=message,
    )


def _groups(state: IdentifyState) -> list[EvidenceWallGroup]:
    evidence_by_id = {item.id: item for item in state.evidence}
    groups: list[EvidenceWallGroup] = []
    used_evidence_ids: set[UUID] = set()

    for area in state.playbook_coverage:
        cards = [
            _card(evidence_by_id[evidence_id])
            for evidence_id in area.evidence_ids
            if evidence_id in evidence_by_id
        ]
        if not cards:
            continue
        used_evidence_ids.update(card.id for card in cards)
        groups.append(
            EvidenceWallGroup(
                id=area.area_id,
                title=area.label,
                status=area.status,
                evidenceCount=len(cards),
                cards=cards[:6],
            )
        )

    uncategorized_cards = [
        _card(item)
        for item in state.evidence
        if item.id not in used_evidence_ids
    ]
    if uncategorized_cards:
        groups.append(
            EvidenceWallGroup(
                id="uncategorized",
                title="Unsorted evidence",
                status="partial",
                evidenceCount=len(uncategorized_cards),
                cards=uncategorized_cards[:6],
            )
        )

    if state.output.cross_check_findings:
        groups.append(
            EvidenceWallGroup(
                id="cross-checks",
                title="Contradictions and checks",
                status="partial",
                evidenceCount=len(state.output.cross_check_findings),
                cards=[
                    EvidenceWallCard(
                        id=finding.id,
                        sourceActivity="cross-check",
                        sourceLabel="Cross-check",
                        claim=finding.explanation,
                        summary=f"Revisit {finding.revisit_activity or finding.topic}",
                        cardType="tension",
                        coverageAreaIds=[finding.topic],
                        evidenceStatus="source-derived",
                        sourceReference=None,
                        derivedFromEvidenceIds=finding.evidence_ids,
                    )
                    for finding in state.output.cross_check_findings[:6]
                ],
            )
        )

    return sorted(groups, key=lambda group: group.evidence_count, reverse=True)


def _card(evidence: IdentifyEvidence) -> EvidenceWallCard:
    activity_id = evidence.source_activity
    return EvidenceWallCard(
        id=evidence.id,
        sourceActivity=activity_id,
        sourceLabel=SOURCE_LABELS.get(activity_id or "", evidence.source.title),
        claim=evidence.claim,
        summary=evidence.summary,
        cardType=_card_type(activity_id),
        coverageAreaIds=evidence.coverage_area_ids,
        evidenceStatus=evidence.evidence_status.value,
        sourceReference=evidence.source_reference,
        derivedFromEvidenceIds=evidence.derived_from_evidence_ids,
    )


def _card_type(activity_id: str | None) -> str:
    if activity_id == "perception-gaps":
        return "tension"
    if activity_id == "day-in-their-shoes":
        return "touch-point"
    if activity_id in {"ai-detective", "signal-hunt", "discover-synthesis"}:
        return "fact"
    return "strength"


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
