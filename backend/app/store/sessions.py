from datetime import datetime
from uuid import UUID

from app.config.settings import settings
from app.schemas.assessment import (
    AssessmentLifecycleStatus,
    AssessmentSession,
    AssessmentSessionCreate,
    AssessmentStage,
    AssessmentStageStatus,
    AlignmentState,
    CompanyCardsEvidence,
    DefineState,
    StressTestState,
    IdentifyEvidence,
    IdentifyCompletionStatus,
    IdentifyOutput,
    IdentifyState,
    ExternalResearchState,
    PerceptionGap,
    PESTLEFinding,
    ResearchFinding,
    IdentifyTheme,
    Stakeholder,
    StakeholderJourney,
    WhereDoYouStandEvidence,
    utc_now,
)
from app.services.define_generation import build_define_output
from app.services.stress_test import build_stress_test_output
from app.services.alignment import build_alignment_output
from app.store.repository import (
    AssessmentRepository,
    InMemoryAssessmentRepository,
    create_assessment_repository,
)
from app.services.identify_foundation import (
    evidence_from_company_cards,
    evidence_from_discover_synthesis,
    evidence_from_perception_gaps,
    evidence_from_research_findings,
    evidence_from_signal_hunt,
    evidence_from_stakeholder_journeys,
    evidence_from_stakeholders,
    evidence_from_where_do_you_stand,
    initialize_identify_foundation,
    refresh_identify_foundation,
    replace_activity_evidence,
)


class IdentifyStageReadOnlyError(RuntimeError):
    """Raised when completed Identify evidence is changed after progression."""


class SessionStore:
    """Assessment operations layered over a replaceable repository adapter."""

    def __init__(self, repository: AssessmentRepository) -> None:
        self._repository = repository

    def create(self, payload: AssessmentSessionCreate) -> AssessmentSession:
        organisation = payload.organisation
        if payload.company_name is not None or payload.website is not None:
            organisation = organisation.model_copy(
                update={
                    "company_name": payload.company_name or organisation.company_name,
                    "website": payload.website or organisation.website,
                }
            )
        session = AssessmentSession(stage=payload.stage, organisation=organisation)
        initialize_identify_foundation(session)
        return self._repository.create(session)

    def get(self, session_id: UUID) -> AssessmentSession | None:
        return self._repository.get(session_id)

    def require_identify_mutable(
        self, session_id: UUID
    ) -> AssessmentSession | None:
        session = self.get(session_id)
        if (
            session is not None
            and session.identify.completion_status
            == IdentifyCompletionStatus.completed
            and session.stage != AssessmentStage.identify
        ):
            raise IdentifyStageReadOnlyError(
                "Completed Identify is available for review only."
            )
        return session

    def save(self, session: AssessmentSession) -> AssessmentSession:
        """Persist a complete assessment after lifecycle or stage changes."""
        session.updated_at = utc_now()
        session.version += 1
        return self._repository.save(session)

    def save_lifecycle_state(
        self,
        session_id: UUID,
        *,
        stage: AssessmentStage,
        lifecycle_status: AssessmentLifecycleStatus,
        stage_state: dict[str, object],
        structured_outputs: dict[AssessmentStage, dict[str, object]],
        handoffs: list[dict[str, object]],
        revisit_routes: list[dict[str, object]],
        next_stage: AssessmentStage | None = None,
        identify_completion_status: IdentifyCompletionStatus | None = None,
        identify_completed_at: datetime | None = None,
    ) -> AssessmentSession | None:
        """Save authoritative lifecycle data without coupling to the orchestrator."""
        session = self.get(session_id)
        if session is None:
            return None
        session.stage = stage
        session.lifecycle_status = lifecycle_status
        session.stage_statuses[stage] = (
            AssessmentStageStatus.completed
            if lifecycle_status == AssessmentLifecycleStatus.stage_completed
            else AssessmentStageStatus.in_progress
        )
        session.stage_states[stage] = stage_state
        session.structured_outputs = structured_outputs
        session.handoffs = handoffs
        session.revisit_routes = revisit_routes
        session.next_stage = next_stage
        if next_stage is not None:
            session.stage_statuses.setdefault(
                next_stage,
                AssessmentStageStatus.not_started,
            )
        if identify_completion_status is not None:
            session.identify.completion_status = identify_completion_status
            session.identify.completed_at = identify_completed_at
            refresh_identify_foundation(session)
        return self.save(session)

    def _save_identify(self, session: AssessmentSession) -> IdentifyState:
        session.identify.updated_at = utc_now()
        self.save(session)
        return session.identify.model_copy(deep=True)

    def get_identify_state(self, session_id: UUID) -> IdentifyState | None:
        session = self.get(session_id)
        if session is None:
            return None
        return session.identify.model_copy(deep=True)

    def get_define_state(self, session_id: UUID) -> DefineState | None:
        session = self.get(session_id)
        if session is None:
            return None
        return session.define.model_copy(deep=True)

    def update_define_state(
        self,
        session_id: UUID,
        define: DefineState,
        *,
        stage: AssessmentStage | None = None,
        lifecycle_status: AssessmentLifecycleStatus | None = None,
        next_stage: AssessmentStage | None = None,
    ) -> DefineState | None:
        session = self.get(session_id)
        if session is None:
            return None

        now = utc_now()
        define.assessment_id = session_id
        define.updated_at = now
        define.version += 1
        define.output = build_define_output(define)
        session.define = define
        session.structured_outputs[AssessmentStage.define] = define.output.model_dump(
            mode="json",
            by_alias=True,
        )
        if stage is not None:
            session.stage = stage
        if lifecycle_status is not None:
            session.lifecycle_status = lifecycle_status
        session.stage_statuses[AssessmentStage.define] = AssessmentStageStatus.in_progress
        if session.stage_statuses.get(AssessmentStage.identify) is None:
            session.stage_statuses[AssessmentStage.identify] = (
                AssessmentStageStatus.completed
            )
        session.next_stage = next_stage
        self.save(session)
        return session.define.model_copy(deep=True)

    def get_stress_test_state(self, session_id: UUID) -> StressTestState | None:
        session = self.get(session_id)
        return None if session is None else session.stress_test.model_copy(deep=True)

    def update_stress_test_state(
        self, session_id: UUID, stress_test: StressTestState, *,
        stage: AssessmentStage = AssessmentStage.stress_test,
        lifecycle_status: AssessmentLifecycleStatus = AssessmentLifecycleStatus.active,
        next_stage: AssessmentStage | None = AssessmentStage.align,
    ) -> StressTestState | None:
        session = self.get(session_id)
        if session is None:
            return None
        stress_test.assessment_id = session_id
        stress_test.updated_at = utc_now()
        stress_test.version += 1
        stress_test.output = build_stress_test_output(stress_test)
        session.stress_test = stress_test
        session.stage = stage
        session.lifecycle_status = lifecycle_status
        session.stage_statuses[AssessmentStage.define] = AssessmentStageStatus.completed
        session.stage_statuses[AssessmentStage.stress_test] = (
            AssessmentStageStatus.completed if stress_test.status == "completed" else AssessmentStageStatus.in_progress
        )
        session.stage_statuses.setdefault(AssessmentStage.align, AssessmentStageStatus.not_started)
        session.next_stage = next_stage
        session.structured_outputs[AssessmentStage.stress_test] = stress_test.output.model_dump(mode="json", by_alias=True)
        self.save(session)
        return session.stress_test.model_copy(deep=True)

    def get_alignment_state(self, session_id: UUID) -> AlignmentState | None:
        session = self.get(session_id)
        return None if session is None else session.alignment.model_copy(deep=True)

    def update_alignment_state(
        self,
        session_id: UUID,
        alignment: AlignmentState,
    ) -> AlignmentState | None:
        session = self.get(session_id)
        if session is None:
            return None
        alignment.assessment_id = session_id
        alignment.updated_at = utc_now()
        alignment.version += 1
        alignment.output = build_alignment_output(alignment)
        session.alignment = alignment
        session.stage = AssessmentStage.align
        session.lifecycle_status = AssessmentLifecycleStatus.active
        session.stage_statuses[AssessmentStage.define] = AssessmentStageStatus.completed
        session.stage_statuses[AssessmentStage.stress_test] = AssessmentStageStatus.completed
        session.stage_statuses[AssessmentStage.align] = AssessmentStageStatus.in_progress
        session.next_stage = None
        session.structured_outputs[AssessmentStage.align] = alignment.output.model_dump(
            mode="json", by_alias=True
        )
        self.save(session)
        return session.alignment.model_copy(deep=True)

    def update_identify_state(
        self,
        session_id: UUID,
        output: IdentifyOutput,
        evidence: list[IdentifyEvidence],
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output = output
        session.identify.evidence = evidence
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_stakeholders(
        self, session_id: UUID, stakeholders: list[Stakeholder]
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.stakeholder_insights = stakeholders
        replace_activity_evidence(
            session.identify,
            "who-matters",
            evidence_from_stakeholders(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_pestle_findings(
        self, session_id: UUID, findings: list[PESTLEFinding]
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.pestle_findings = findings
        replace_activity_evidence(
            session.identify,
            "signal-hunt",
            evidence_from_signal_hunt(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_research_findings(
        self, session_id: UUID, findings: list[ResearchFinding]
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.research_findings = findings
        replace_activity_evidence(
            session.identify,
            "ai-detective",
            evidence_from_research_findings(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_ai_detective_research(
        self,
        session_id: UUID,
        *,
        findings: list[ResearchFinding],
        external_research: ExternalResearchState,
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.research_findings = findings
        session.identify.output.external_research = external_research
        replace_activity_evidence(
            session.identify,
            "ai-detective",
            evidence_from_research_findings(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_discovery_brief(
        self,
        session_id: UUID,
        discovery_brief: str,
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.discovery_brief = discovery_brief
        replace_activity_evidence(
            session.identify,
            "discover-synthesis",
            evidence_from_discover_synthesis(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_company_cards(
        self, session_id: UUID, evidence: CompanyCardsEvidence
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.company_cards_evidence = evidence
        replace_activity_evidence(
            session.identify,
            "company-cards",
            evidence_from_company_cards(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_stakeholder_journeys(
        self, session_id: UUID, journeys: list[StakeholderJourney]
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.stakeholder_journeys = journeys
        replace_activity_evidence(
            session.identify,
            "day-in-their-shoes",
            evidence_from_stakeholder_journeys(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_where_do_you_stand(
        self,
        session_id: UUID,
        evidence: WhereDoYouStandEvidence,
        positioning_evidence: list[IdentifyEvidence],
        social_contribution_evidence: list[IdentifyEvidence],
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.where_do_you_stand_evidence = evidence
        session.identify.output.positioning_evidence = positioning_evidence
        session.identify.output.social_contribution_evidence = (
            social_contribution_evidence
        )
        replace_activity_evidence(
            session.identify,
            "where-do-you-stand",
            evidence_from_where_do_you_stand(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_perception_gaps(
        self, session_id: UUID, gaps: list[PerceptionGap]
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.perception_gaps = gaps
        session.identify.output.vulnerabilities_gaps = [
            gap.difference for gap in gaps if gap.resolution != "confirmed"
        ]
        replace_activity_evidence(
            session.identify,
            "perception-gaps",
            evidence_from_perception_gaps(session.identify),
        )
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def update_identify_themes(
        self, session_id: UUID, themes: list[IdentifyTheme]
    ) -> IdentifyState | None:
        session = self.require_identify_mutable(session_id)
        if session is None:
            return None

        session.identify.output.themes = themes
        refresh_identify_foundation(session)
        return self._save_identify(session)

    def clear(self) -> None:
        self._repository.clear()


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        super().__init__(InMemoryAssessmentRepository())


session_store = SessionStore(
    create_assessment_repository(
        settings.assessment_repository,
        supabase_url=settings.supabase_url,
        supabase_service_role_key=settings.supabase_service_role_key,
    )
)
