from app.schemas.assessment import (
    AssessmentSession,
    DefineApprovalStatus,
    DefineStatus,
)
from app.schemas.define_completion import (
    DefineCompletionIssue,
    DefineCompletionReadiness,
)
from app.services.define_evidence import get_define_evidence_ids
from app.services.define_questions import present_define_questions


def evaluate_define_readiness(session: AssessmentSession) -> DefineCompletionReadiness:
    """Apply deterministic, non-scored readiness rules before Stress Test."""
    state = session.define
    blockers: list[DefineCompletionIssue] = []
    soi = state.soi_candidate
    if (
        soi is None
        or not soi.statement
        or soi.approval_status != DefineApprovalStatus.agreed
    ):
        blockers.append(_issue("agreed-soi", "Agree a usable Single Organizing Idea."))
    positioning = state.positioning
    if positioning.approval_status != DefineApprovalStatus.agreed or not all(
        [
            positioning.audience,
            positioning.category_context,
            positioning.capability_value,
            positioning.reason_believability,
        ]
    ):
        blockers.append(
            _issue(
                "agreed-positioning",
                "Agree all four Positioning Statement parts.",
            )
        )
    if not any(
        item.approval_status == DefineApprovalStatus.agreed for item in state.values
    ):
        blockers.append(
            _issue(
                "agreed-values",
                "Agree at least one Core Value or commitment.",
            )
        )
    if not any(
        item.approval_status == DefineApprovalStatus.agreed for item in state.moments
    ):
        blockers.append(
            _issue(
                "agreed-moments",
                "Agree at least one relevant Moment of Truth.",
            )
        )

    known = get_define_evidence_ids(session)
    referenced = set(state.evidence_references)
    invalid = referenced - known
    if not referenced:
        blockers.append(
            _issue(
                "define-evidence",
                "Define needs evidence references from Identify.",
            )
        )
    if invalid:
        blockers.append(
            DefineCompletionIssue(
                code="invalid-evidence",
                message="Define contains unresolved evidence references.",
                evidenceIds=sorted(invalid, key=str),
            )
        )
    completed = state.status == DefineStatus.completed
    return DefineCompletionReadiness(
        status=(
            DefineStatus.completed
            if completed
            else DefineStatus.ready_for_review
            if not blockers
            else DefineStatus.in_progress
        ),
        canComplete=completed or not blockers,
        blockingIssues=blockers,
        openQuestions=present_define_questions(state.unresolved_questions),
    )


def _issue(code: str, message: str) -> DefineCompletionIssue:
    return DefineCompletionIssue(code=code, message=message)
