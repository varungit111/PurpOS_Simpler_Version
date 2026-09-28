from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import AssessmentSession, IdentifyEvidence, IdentifyState
from app.schemas.identify_brief import (
    IdentifyBriefCoverageArea,
    IdentifyBriefEvidence,
    IdentifyBriefQuestion,
    IdentifyBriefReadiness,
    IdentifyBriefResponse,
    IdentifyBriefSourceBreakdown,
    IdentifyBriefTheme,
)
from app.orchestrator.orchestrator import (
    IdentifyCompletionBlockedError,
    SessionNotFoundError,
    orchestrator,
)
from app.schemas.identify_completion import IdentifyCompletionResponse
from app.services.identify_completion import get_persisted_identify_handoff
from app.services.identify_readiness import evaluate_identify_readiness
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["identify-brief"])

DISCOVER_ACTIVITIES = {"ai-detective", "signal-hunt", "discover-synthesis"}
LISTEN_ACTIVITIES = {"who-matters", "hot-seat", "company-cards", "listen-summary"}
UNDERSTAND_ACTIVITIES = {
    "day-in-their-shoes",
    "where-do-you-stand",
    "perception-gaps",
    "evidence-wall",
}

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
    "evidence-wall": "Evidence Wall",
}


@router.get(
    "/{session_id}/identify/brief",
    response_model=IdentifyBriefResponse,
)
def get_identify_brief(session_id: UUID) -> IdentifyBriefResponse:
    session = session_store.get(session_id)
    if session is None:
        raise _session_not_found()

    return build_identify_brief(session)


@router.get(
    "/{session_id}/identify/completion",
    response_model=IdentifyCompletionResponse,
)
def get_identify_completion(session_id: UUID) -> IdentifyCompletionResponse:
    session = session_store.get(session_id)
    if session is None:
        raise _session_not_found()
    return IdentifyCompletionResponse(
        readiness=evaluate_identify_readiness(session),
        handoff=get_persisted_identify_handoff(session),
    )


@router.post(
    "/{session_id}/identify/complete",
    response_model=IdentifyCompletionResponse,
)
def complete_identify(session_id: UUID) -> IdentifyCompletionResponse:
    try:
        session_store.require_identify_mutable(session_id)
        orchestrator.complete_identify(session_id)
    except IdentifyCompletionBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.readiness.model_dump(mode="json", by_alias=True),
        ) from exc
    except SessionNotFoundError as exc:
        raise _session_not_found() from exc

    session = session_store.get(session_id)
    if session is None:
        raise _session_not_found()
    return IdentifyCompletionResponse(
        readiness=evaluate_identify_readiness(session),
        handoff=get_persisted_identify_handoff(session),
    )


def build_identify_brief(session: AssessmentSession) -> IdentifyBriefResponse:
    state = session.identify
    evidence_by_id = {item.id: item for item in state.evidence}
    themes = _themes(state, evidence_by_id)
    strongest_evidence = _strongest_evidence(state)
    open_questions = _open_questions(state)
    readiness = _readiness(session)
    organisation_name = session.organisation.company_name or "Your organisation"

    return IdentifyBriefResponse(
        organisationName=organisation_name,
        website=str(session.organisation.website) if session.organisation.website else None,
        statement=_statement(organisation_name, themes, readiness),
        evidenceCount=len(state.evidence),
        sourceBreakdown=_source_breakdown(state),
        themes=themes,
        strongestEvidence=strongest_evidence,
        openQuestions=open_questions,
        coverage=[
            IdentifyBriefCoverageArea(
                areaId=area.area_id,
                label=area.label,
                question=area.question,
                status=area.status,
                evidenceCount=len(area.evidence_ids),
            )
            for area in state.playbook_coverage
        ],
        unresolvedGapCount=len(_unresolved_gaps(state)),
        readiness=readiness,
        handoffLabel=(
            "Ready for Define"
            if readiness.is_ready
            else "Keep gathering Identify evidence"
        ),
    )


def _themes(
    state: IdentifyState,
    evidence_by_id: dict[UUID, IdentifyEvidence],
) -> list[IdentifyBriefTheme]:
    if state.output.themes:
        return [
            IdentifyBriefTheme(
                id=theme.id,
                name=theme.name,
                summary=theme.summary,
                evidenceCount=len(theme.evidence_ids),
                evidenceIds=theme.evidence_ids,
                isLead=index == 0,
            )
            for index, theme in enumerate(state.output.themes[:5])
        ]

    coverage_by_id = {
        area.area_id: area for area in state.playbook_coverage if area.evidence_ids
    }
    fallback_themes: list[IdentifyBriefTheme] = []
    for area in sorted(
        coverage_by_id.values(),
        key=lambda item: len(item.evidence_ids),
        reverse=True,
    )[:5]:
        evidence_ids = [
            evidence_id
            for evidence_id in area.evidence_ids
            if evidence_id in evidence_by_id
        ]
        fallback_themes.append(
            IdentifyBriefTheme(
                id=evidence_ids[0],
                name=area.label,
                summary=(
                    f"{len(evidence_ids)} evidence item"
                    f"{'s' if len(evidence_ids) != 1 else ''} linked to "
                    f"{area.question}"
                ),
                evidenceCount=len(evidence_ids),
                evidenceIds=evidence_ids,
                isLead=len(fallback_themes) == 0,
            )
        )
    return fallback_themes


def _strongest_evidence(state: IdentifyState) -> list[IdentifyBriefEvidence]:
    evidence_area_counts = {
        item.id: len(item.coverage_area_ids)
        for item in state.evidence
    }
    return [
        _brief_evidence(item)
        for item in sorted(
            state.evidence,
            key=lambda item: (
                evidence_area_counts[item.id],
                1 if item.source_activity in UNDERSTAND_ACTIVITIES else 0,
            ),
            reverse=True,
        )[:6]
    ]


def _open_questions(state: IdentifyState) -> list[IdentifyBriefQuestion]:
    questions = [
        IdentifyBriefQuestion(
            id=f"open-{index + 1}",
            question=question,
            source="Open question",
        )
        for index, question in enumerate(state.output.open_questions[:4])
    ]
    questions.extend(
        IdentifyBriefQuestion(
            id=f"gap-{gap.id}",
            question=gap.difference,
            source="Perception Gap",
            supportingEvidenceIds=gap.supporting_evidence_ids,
        )
        for gap in _unresolved_gaps(state)[:4]
    )
    questions.extend(
        IdentifyBriefQuestion(
            id=f"cross-check-{finding.id}",
            question=finding.explanation,
            source="Cross-check",
            supportingEvidenceIds=finding.evidence_ids,
        )
        for finding in state.output.cross_check_findings[:4]
    )
    uncovered = [
        area for area in state.playbook_coverage if area.status == "uncovered"
    ]
    questions.extend(
        IdentifyBriefQuestion(
            id=f"coverage-{area.area_id}",
            question=area.question,
            source="Coverage gap",
            supportingEvidenceIds=[],
        )
        for area in uncovered[: max(0, 6 - len(questions))]
    )
    return questions[:6]


def _readiness(session: AssessmentSession) -> IdentifyBriefReadiness:
    state = session.identify
    completion = evaluate_identify_readiness(session)
    labels = {
        "organisation-context": "Organisation context",
        "discover-evidence": "Discover evidence",
        "listen-evidence": "Listen evidence",
        "understand-evidence": "Understand evidence",
        "evidence-wall-theme": "Evidence Wall theme",
        "coverage": "20-question coverage evidence",
    }
    missing = [
        labels.get(issue.code, issue.message)
        for issue in completion.blocking_issues
    ]

    covered_area_count = len(
        [
            area
            for area in state.playbook_coverage
            if area.status in {"partial", "sufficient"}
        ]
    )
    return IdentifyBriefReadiness(
        isReady=completion.can_complete,
        coveredAreaCount=covered_area_count,
        totalAreaCount=max(len(state.playbook_coverage), 1),
        requiredEvidenceSources=["Discover", "Listen", "Understand", "Evidence Wall"],
        missing=missing,
    )


def _source_breakdown(state: IdentifyState) -> IdentifyBriefSourceBreakdown:
    discover = 0
    listen = 0
    understand = 0
    for evidence in state.evidence:
        if evidence.source_activity in DISCOVER_ACTIVITIES:
            discover += 1
        elif evidence.source_activity in LISTEN_ACTIVITIES:
            listen += 1
        elif evidence.source_activity in UNDERSTAND_ACTIVITIES:
            understand += 1
    return IdentifyBriefSourceBreakdown(
        discover=discover,
        listen=listen,
        understand=understand,
    )


def _statement(
    organisation_name: str,
    themes: list[IdentifyBriefTheme],
    readiness: IdentifyBriefReadiness,
) -> str:
    if themes:
        lead = themes[0]
        return (
            f"{organisation_name}'s Identify evidence is organised around "
            f"{lead.name}, supported by {lead.evidence_count} evidence item"
            f"{'s' if lead.evidence_count != 1 else ''}."
        )
    if readiness.is_ready:
        return f"{organisation_name}'s Identify evidence is ready for Define."
    return (
        f"{organisation_name}'s Identify brief is still forming from saved "
        "Discover, Listen and Understand evidence."
    )


def _brief_evidence(evidence: IdentifyEvidence) -> IdentifyBriefEvidence:
    activity_id = evidence.source_activity
    return IdentifyBriefEvidence(
        id=evidence.id,
        sourceActivity=activity_id,
        sourceLabel=SOURCE_LABELS.get(activity_id or "", evidence.source.title),
        claim=evidence.claim,
        summary=evidence.summary,
        coverageAreaIds=evidence.coverage_area_ids,
        evidenceStatus=evidence.evidence_status.value,
        sourceReference=evidence.source_reference,
        derivedFromEvidenceIds=evidence.derived_from_evidence_ids,
    )


def _unresolved_gaps(state: IdentifyState):
    return [
        gap
        for gap in state.output.perception_gaps
        if gap.clarification_needed or gap.resolution != "confirmed"
    ]


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
