import json
import unittest
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from app.orchestrator.orchestrator import PurpOSOrchestrator
from app.schemas.assessment import (
    AssessmentSession,
    AssessmentSessionCreate,
    AssessmentStage,
    AssessmentStageStatus,
    DefineApprovalStatus,
    DecisionCanvas,
    SuggestedMove,
    DefineOutput,
    DefineProvenance,
    DefineStatus,
    EvidenceSource,
    EvidenceStatus,
    IdentifyEvidence,
    IdentifyTheme,
    ValueChainMoment,
    ValueChainMomentStatus,
    StressTestStatus,
)
from app.services.stress_test import build_stress_test_output, evaluate_stress_test
from app.services.define_evidence import DefineEvidenceRecord
from app.services.alignment import adopt_move, initialize_alignment
from app.store.repository import (
    InMemoryAssessmentRepository,
    create_assessment_repository,
)
from app.store.sessions import SessionStore
from app.store.supabase import (
    AssessmentRepositoryConfigurationError,
    AssessmentRepositoryConflictError,
    AssessmentRepositoryError,
    RestResponse,
    SupabaseAssessmentRepository,
)


class StatefulRestTransport:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}
        self.failure_status: int | None = None
        self.last_headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> RestResponse:
        self.last_headers = headers
        if self.failure_status is not None:
            return RestResponse(self.failure_status, b'{"message":"database down"}')

        query = parse_qs(urlparse(url).query)
        requested_id = query.get("id", [""])[0].removeprefix("eq.")
        expected_version = query.get("version", [""])[0].removeprefix("eq.")
        payload = None if body is None else json.loads(body.decode("utf-8"))

        if method == "POST":
            assert isinstance(payload, dict)
            row_id = str(payload["id"])
            if row_id in self.rows:
                return RestResponse(409, b'{"message":"duplicate key"}')
            self.rows[row_id] = payload
            return self._rows([payload])
        if method == "GET":
            row = self.rows.get(requested_id)
            return self._rows([] if row is None else [row])
        if method == "PATCH":
            assert isinstance(payload, dict)
            if requested_id not in self.rows:
                return self._rows([])
            stored_version = str(self.rows[requested_id]["version"])
            if expected_version and stored_version != expected_version:
                return self._rows([])
            self.rows[requested_id] = payload
            return self._rows([payload])
        raise AssertionError(f"Unexpected HTTP method {method}")

    def _rows(self, rows: list[dict[str, object]]) -> RestResponse:
        return RestResponse(200, json.dumps(rows).encode("utf-8"))


def repository(transport: StatefulRestTransport) -> SupabaseAssessmentRepository:
    return SupabaseAssessmentRepository(
        "https://project.supabase.co",
        "service-role-test-key",
        transport=transport,
    )


class SupabaseAssessmentRepositoryTests(unittest.TestCase):
    def test_create_and_get_round_trip_complete_session(self) -> None:
        transport = StatefulRestTransport()
        repo = repository(transport)
        session = AssessmentSession()

        created = repo.create(session)
        loaded = repo.get(session.id)

        self.assertEqual(created, session)
        self.assertEqual(loaded, session)
        self.assertEqual(transport.last_headers["apikey"], "service-role-test-key")
        self.assertEqual(
            transport.last_headers["Authorization"],
            "Bearer service-role-test-key",
        )

    def test_save_updates_existing_record(self) -> None:
        transport = StatefulRestTransport()
        repo = repository(transport)
        session = repo.create(AssessmentSession())
        session.version = 2
        session.identify.output.discovery_brief = "Evidence-backed purpose context."

        saved = repo.save(session)

        self.assertEqual(saved.version, 2)
        self.assertEqual(
            repo.get(session.id).identify.output.discovery_brief,  # type: ignore[union-attr]
            "Evidence-backed purpose context.",
        )

    def test_define_moment_survives_supabase_round_trip(self) -> None:
        transport = StatefulRestTransport()
        repo = repository(transport)
        session = AssessmentSession()
        evidence_id = uuid4()
        moment = ValueChainMoment(
            name="Customer onboarding",
            question="How should a customer experience the first month?",
            today="The experience varies by account owner.",
            desiredState="Every customer receives a confident start.",
            theMove="Adopt one onboarding standard.",
            status=ValueChainMomentStatus.gap_to_close,
            supportingEvidence=["Customers asked for clearer handoffs."],
            evidenceIds=[evidence_id],
            provenance=DefineProvenance(
                status=EvidenceStatus.user_confirmed,
                rationale="Reviewed during Define.",
                sourceHandoff="structured_outputs.identify.handoff",
            ),
            approvalStatus=DefineApprovalStatus.agreed,
        )
        session.define.status = DefineStatus.in_progress
        session.define.moments = [moment]

        repo.create(session)
        loaded = repository(transport).get(session.id)

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.define.moments, [moment])
        self.assertEqual(loaded.define.moments[0].id, moment.id)
        self.assertEqual(loaded.define.moments[0].evidence_ids, [evidence_id])

    def test_stress_test_survives_supabase_round_trip_and_restart(self) -> None:
        transport = StatefulRestTransport()
        repo = repository(transport)
        session = AssessmentSession()
        evidence_id = uuid4()
        session.stress_test = evaluate_stress_test(
            session.id,
            DefineOutput(evidenceReferences=[evidence_id]),
            evidence_records={
                evidence_id: DefineEvidenceRecord(
                    id=evidence_id,
                    kind="identify-evidence",
                    title="Operating evidence",
                    text="Documented governance and operating facts.",
                    coverage_area_ids=("organisation_basics",),
                )
            },
        )
        session.stage = AssessmentStage.stress_test
        session.stage_statuses[AssessmentStage.define] = AssessmentStageStatus.completed
        session.stage_statuses[AssessmentStage.stress_test] = AssessmentStageStatus.in_progress
        session.next_stage = AssessmentStage.align
        repo.create(session)

        restarted_store = SessionStore(repository(transport))
        loaded = restarted_store.get(session.id)

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(len(loaded.stress_test.criteria), 8)
        self.assertEqual(loaded.stress_test.evidence_references, [evidence_id])
        self.assertEqual(loaded.stress_test.criteria[0].supporting_evidence_ids, [evidence_id])

    def test_alignment_decisions_and_adoption_survive_supabase_restart(self) -> None:
        transport = StatefulRestTransport()
        repo = repository(transport)
        session = AssessmentSession()
        evidence_id = uuid4()
        session.define.output = DefineOutput(evidenceReferences=[evidence_id])
        stress = evaluate_stress_test(session.id, session.define.output)
        stress.status = StressTestStatus.completed
        stress.output = build_stress_test_output(stress)
        session.stress_test = stress
        session.alignment = initialize_alignment(
            session.id, session.define.output, stress.output
        )
        session.stage = AssessmentStage.align
        session.stage_statuses[AssessmentStage.align] = AssessmentStageStatus.in_progress
        decision = DecisionCanvas(originalQuestion="Should we expand?")
        move = SuggestedMove(
            action="Run a bounded pilot.",
            rationale="Test the reviewed tension before scaling.",
            relatedDecisionId=decision.id,
            evidenceReferences=[evidence_id],
        )
        adopted_move, adopted_action = adopt_move(move)
        decision.suggested_moves = [adopted_move]
        decision.adopted_action_ids = [adopted_action.id]
        session.alignment.decisions.append(decision)
        session.alignment.adopted_actions.append(adopted_action)
        repo.create(session)

        loaded = SessionStore(repository(transport)).get(session.id)

        assert loaded is not None
        self.assertEqual(loaded.alignment.decisions[0].original_question, "Should we expand?")
        self.assertEqual(loaded.alignment.evidence_references, [evidence_id])
        self.assertTrue(loaded.alignment.decisions[0].suggested_moves[0].adopted)
        self.assertEqual(
            loaded.alignment.adopted_actions[0].source_move_id,
            move.id,
        )
        self.assertEqual(
            loaded.alignment.adopted_actions[0].provenance.status,
            "user-confirmed",
        )

    def test_get_missing_record_returns_none(self) -> None:
        self.assertIsNone(repository(StatefulRestTransport()).get(uuid4()))

    def test_save_missing_record_raises_key_error(self) -> None:
        repo = repository(StatefulRestTransport())

        with self.assertRaises(KeyError):
            repo.save(AssessmentSession())

    def test_duplicate_create_raises_conflict(self) -> None:
        repo = repository(StatefulRestTransport())
        session = AssessmentSession()
        repo.create(session)

        with self.assertRaises(AssessmentRepositoryConflictError):
            repo.create(session)

    def test_stale_save_raises_conflict(self) -> None:
        repo = repository(StatefulRestTransport())
        session = repo.create(AssessmentSession())
        newer = session.model_copy(update={"version": 2})
        repo.save(newer)
        stale = session.model_copy(update={"version": 2})

        with self.assertRaises(AssessmentRepositoryConflictError):
            repo.save(stale)

    def test_database_errors_are_not_swallowed(self) -> None:
        transport = StatefulRestTransport()
        transport.failure_status = 503

        with self.assertRaisesRegex(AssessmentRepositoryError, "HTTP 503"):
            repository(transport).get(uuid4())

    def test_identify_evidence_survives_repository_recreation(self) -> None:
        transport = StatefulRestTransport()
        first_store = SessionStore(repository(transport))
        session = first_store.create(AssessmentSessionCreate())
        state = first_store.get_identify_state(session.id)
        assert state is not None
        evidence = IdentifyEvidence(
            source=EvidenceSource(title="Interview", source_type="hot_seat"),
            claim="Customers describe delivery as trusted and reliable.",
            sourceActivity="hot-seat",
            coverageAreaIds=["customer_needs"],
            evidenceStatus="user-confirmed",
            sourceReference="conversation-turn:test",
        )
        contrasting_evidence = IdentifyEvidence(
            source=EvidenceSource(title="Journey", source_type="journey"),
            claim="Customers describe delivery as unreliable and inconsistent.",
            sourceActivity="day-in-their-shoes",
            coverageAreaIds=["customer_needs"],
        )
        first_store.update_identify_state(
            session.id,
            state.output,
            [evidence, contrasting_evidence],
        )

        restarted_store = SessionStore(repository(transport))
        loaded = restarted_store.get(session.id)

        assert loaded is not None
        self.assertEqual(loaded.identify.evidence[0].id, evidence.id)
        self.assertEqual(loaded.identify.evidence[0].evidence_status, "user-confirmed")
        self.assertEqual(
            loaded.identify.evidence[0].source_reference,
            "conversation-turn:test",
        )
        self.assertEqual(
            loaded.identify.output.cross_check_findings[0].evidence_ids,
            [evidence.id, contrasting_evidence.id],
        )
        customer_coverage = next(
            item
            for item in loaded.identify.playbook_coverage
            if item.area_id == "customer_needs"
        )
        self.assertEqual(
            customer_coverage.evidence_ids,
            [evidence.id, contrasting_evidence.id],
        )

    def test_orchestrator_reconstructs_from_durable_repository_state(self) -> None:
        transport = StatefulRestTransport()
        durable_store = SessionStore(repository(transport))
        session = durable_store.create(AssessmentSessionCreate())

        # Orchestrator accepts the same SessionStore contract; swap the module-level
        # facade only inside this test to simulate a process using Supabase.
        import app.orchestrator.orchestrator as orchestrator_module

        original_store = orchestrator_module.session_store
        orchestrator_module.session_store = durable_store
        try:
            first = PurpOSOrchestrator()
            state = first.get_state(session.id)
            first.handle_message(
                state.session_id,
                "We build scheduling software for regional clinics.",
            )
            resumed = PurpOSOrchestrator().get_state(session.id)
        finally:
            orchestrator_module.session_store = original_store

        self.assertEqual(
            resumed.context.collected_fields["discovery_brief"],
            "We build scheduling software for regional clinics.",
        )
        self.assertIn("identify", resumed.structured_outputs)

    def test_completed_identify_handoff_survives_repository_recreation(self) -> None:
        transport = StatefulRestTransport()
        durable_store = SessionStore(repository(transport))
        session = durable_store.create(
            AssessmentSessionCreate(companyName="Meridian")
        )
        state = durable_store.get_identify_state(session.id)
        assert state is not None
        evidence = [
            IdentifyEvidence(
                source=EvidenceSource(title="Research", source_type="sme-provided"),
                claim="Clinic operators need reliable appointment workflows.",
                sourceActivity="ai-detective",
                coverageAreaIds=["customer_needs"],
            ),
            IdentifyEvidence(
                source=EvidenceSource(title="Interview", source_type="interview"),
                claim="Clinic managers value clear support during onboarding.",
                sourceActivity="who-matters",
                coverageAreaIds=["customer_needs"],
            ),
            IdentifyEvidence(
                source=EvidenceSource(title="Positioning", source_type="workshop"),
                claim="The organisation is positioned around dependable service.",
                sourceActivity="where-do-you-stand",
                coverageAreaIds=["market_position"],
            ),
        ]
        state.output.themes = [
            IdentifyTheme(
                name="Dependable service",
                summary="Reliability links customer need and market position.",
                evidence_ids=[item.id for item in evidence],
            )
        ]
        state.output.evidence_references = [item.id for item in evidence]
        durable_store.update_identify_state(session.id, state.output, evidence)

        import app.orchestrator.orchestrator as orchestrator_module

        original_store = orchestrator_module.session_store
        orchestrator_module.session_store = durable_store
        try:
            PurpOSOrchestrator().complete_identify(session.id)
        finally:
            orchestrator_module.session_store = original_store

        restarted_store = SessionStore(repository(transport))
        loaded = restarted_store.get(session.id)

        assert loaded is not None
        self.assertEqual(loaded.lifecycle_status, "stage_completed")
        self.assertEqual(loaded.next_stage, "define")
        self.assertEqual(loaded.stage_statuses["identify"], "completed")
        self.assertEqual(loaded.stage_statuses["define"], "not_started")
        self.assertEqual(loaded.identify.completion_status, "completed")
        handoff = loaded.structured_outputs["identify"]["handoff"]
        self.assertEqual(handoff["assessmentId"], str(session.id))
        self.assertEqual(handoff["evidenceReferences"], [str(item.id) for item in evidence])


class AssessmentRepositoryFactoryTests(unittest.TestCase):
    def test_memory_selection(self) -> None:
        selected = create_assessment_repository("memory")

        self.assertIsInstance(selected, InMemoryAssessmentRepository)

    def test_supabase_selection_requires_credentials(self) -> None:
        with self.assertRaises(AssessmentRepositoryConfigurationError):
            create_assessment_repository("supabase")

    def test_supabase_selection(self) -> None:
        selected = create_assessment_repository(
            "supabase",
            supabase_url="https://project.supabase.co",
            supabase_service_role_key="backend-only-key",
        )

        self.assertIsInstance(selected, SupabaseAssessmentRepository)

    def test_unknown_selection_fails_clearly(self) -> None:
        with self.assertRaises(AssessmentRepositoryConfigurationError):
            create_assessment_repository("automatic")


if __name__ == "__main__":
    unittest.main()
