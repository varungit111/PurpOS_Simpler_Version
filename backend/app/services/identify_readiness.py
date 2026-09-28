from app.schemas.assessment import (
    AssessmentSession,
    IdentifyCompletionStatus,
    PerceptionGapResolution,
)
from app.schemas.identify_completion import (
    IdentifyCompletionIssue,
    IdentifyCompletionReadiness,
)


DISCOVER_ACTIVITIES = {"ai-detective", "signal-hunt", "discover-synthesis"}
LISTEN_ACTIVITIES = {"who-matters", "hot-seat", "company-cards", "listen-summary"}
UNDERSTAND_ACTIVITIES = {
    "day-in-their-shoes",
    "where-do-you-stand",
    "perception-gaps",
}


def evaluate_identify_readiness(
    session: AssessmentSession,
) -> IdentifyCompletionReadiness:
    """Evaluate explicit Identify outputs without using a score or percentage."""
    state = session.identify
    blocking: list[IdentifyCompletionIssue] = []
    source_activities = {
        item.source_activity for item in state.evidence if item.source_activity
    }

    if not session.organisation.company_name:
        blocking.append(
            _issue("organisation-context", "Organisation context is required.", "who-are-you")
        )
    if not source_activities & DISCOVER_ACTIVITIES:
        blocking.append(_issue("discover-evidence", "Discover evidence is required.", "ai-detective"))
    if not source_activities & LISTEN_ACTIVITIES:
        blocking.append(_issue("listen-evidence", "Listen evidence is required.", "who-matters"))
    if not source_activities & UNDERSTAND_ACTIVITIES:
        blocking.append(
            _issue("understand-evidence", "Understand evidence is required.", "where-do-you-stand")
        )
    if not state.output.themes:
        blocking.append(_issue("evidence-wall-theme", "An Evidence Wall theme is required.", "evidence-wall"))
    if not any(area.evidence_ids for area in state.playbook_coverage):
        blocking.append(_issue("coverage", "At least one guided evidence area must be supported."))

    known_evidence_ids = {item.id for item in state.evidence}
    invalid_references = [
        evidence_id
        for evidence_id in state.output.evidence_references
        if evidence_id not in known_evidence_ids
    ]
    if invalid_references:
        blocking.append(
            IdentifyCompletionIssue(
                code="invalid-evidence-reference",
                message="Identify contains evidence references that cannot be resolved.",
                evidenceIds=invalid_references,
            )
        )
    missing_references = known_evidence_ids - set(state.output.evidence_references)
    if missing_references:
        blocking.append(
            IdentifyCompletionIssue(
                code="missing-evidence-reference",
                message="Some Identify evidence is missing from the final reference list.",
                evidenceIds=sorted(missing_references, key=str),
            )
        )

    resolved_cross_checks = _resolved_cross_check_evidence_sets(session)
    for finding in state.output.cross_check_findings:
        evidence_set = frozenset(finding.evidence_ids)
        if evidence_set not in resolved_cross_checks:
            blocking.append(
                IdentifyCompletionIssue(
                    code="unresolved-cross-check",
                    message=finding.explanation,
                    activityId=finding.revisit_activity,
                    evidenceIds=finding.evidence_ids,
                )
            )

    for gap in state.output.perception_gaps:
        if (
            gap.clarification_needed
            and gap.resolution == PerceptionGapResolution.unresolved
            and frozenset(gap.supporting_evidence_ids) not in {
                frozenset(item.evidence_ids)
                for item in state.output.cross_check_findings
            }
        ):
            blocking.append(
                IdentifyCompletionIssue(
                    code="unresolved-perception-gap",
                    message=gap.difference,
                    activityId="perception-gaps",
                    evidenceIds=gap.supporting_evidence_ids,
                )
            )

    open_questions = _open_questions(session)
    completed = state.completion_status == IdentifyCompletionStatus.completed
    return IdentifyCompletionReadiness(
        status=(
            IdentifyCompletionStatus.completed
            if completed
            else IdentifyCompletionStatus.ready_for_review
            if not blocking
            else IdentifyCompletionStatus.in_progress
        ),
        canComplete=completed or not blocking,
        blockingIssues=blocking,
        openQuestions=open_questions,
    )


def _resolved_cross_check_evidence_sets(
    session: AssessmentSession,
) -> set[frozenset]:
    return {
        frozenset(gap.supporting_evidence_ids)
        for gap in session.identify.output.perception_gaps
        if not gap.clarification_needed
        and gap.resolution != PerceptionGapResolution.unresolved
    }


def _open_questions(session: AssessmentSession) -> list[str]:
    state = session.identify
    questions = list(state.output.open_questions)
    questions.extend(
        area.question
        for area in state.playbook_coverage
        if area.status == "uncovered"
    )
    questions.extend(
        route.get("reason", "Revisit requested.")
        for route in session.revisit_routes
    )
    return list(dict.fromkeys(questions))


def _issue(code: str, message: str, activity_id: str | None = None) -> IdentifyCompletionIssue:
    return IdentifyCompletionIssue(code=code, message=message, activityId=activity_id)
