from datetime import datetime

from app.schemas.assessment import (
    AssessmentStage,
    AssessmentSession,
    IdentifyCompletionStatus,
)
from app.schemas.identify_completion import (
    IdentifyCompletionReadiness,
    IdentifyHandoff,
    IdentifyHandoffRevisit,
)


def build_identify_handoff(
    session: AssessmentSession,
    readiness: IdentifyCompletionReadiness,
    completed_at: datetime,
) -> IdentifyHandoff:
    """Freeze the structured Identify state needed by the future Define stage."""
    # Imported lazily to keep the API module's router imports acyclic while the
    # existing brief builder is shared with this lifecycle checkpoint.
    from app.api.identify_brief import build_identify_brief

    brief = build_identify_brief(session)
    return IdentifyHandoff(
        assessmentId=session.id,
        completionStatus=IdentifyCompletionStatus.completed,
        completedAt=completed_at,
        output=session.identify.output,
        brief=brief,
        coverage=session.identify.playbook_coverage,
        strongestEvidenceIds=[item.id for item in brief.strongest_evidence],
        evidenceReferences=session.identify.output.evidence_references,
        openQuestions=readiness.open_questions,
        revisitHistory=[
            IdentifyHandoffRevisit.model_validate(route)
            for route in session.revisit_routes
        ],
    )


def get_persisted_identify_handoff(
    session: AssessmentSession,
) -> IdentifyHandoff | None:
    output = session.structured_outputs.get(AssessmentStage.identify, {})
    handoff = output.get("handoff")
    if handoff is None:
        return None
    return IdentifyHandoff.model_validate(handoff)
