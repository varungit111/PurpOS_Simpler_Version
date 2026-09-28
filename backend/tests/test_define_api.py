import unittest
from uuid import UUID, uuid4

from backend.tests.test_identify_brief_api import complete_identify_inputs, request
from app.orchestrator.orchestrator import PurpOSOrchestrator
from app.schemas.assessment import DefineApprovalStatus, EvidenceStatus
from app.store.sessions import session_store


class DefineEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_define_generation_requires_completed_identify_handoff(self) -> None:
        created = request("POST", "/api/sessions", {"companyName": "Meridian"}).json()

        response = request(
            "POST",
            f"/api/sessions/{created['id']}/define/generate",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Identify must be completed", response.json()["detail"])

    def test_generate_define_initializes_stage_from_identify_handoff(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")

        response = request("POST", f"/api/sessions/{session_id}/define/generate")

        self.assertEqual(response.status_code, 200)
        define = response.json()["define"]
        self.assertEqual(define["status"], "in_progress")
        self.assertEqual(define["sourceHandoff"], "structured_outputs.identify.handoff")
        self.assertIsNotNone(define["soiCandidate"])
        self.assertEqual(
            define["soiCandidate"]["approvalStatus"],
            "ai-proposed",
        )
        self.assertGreater(len(define["values"]), 0)
        self.assertGreater(len(define["moments"]), 0)

        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(session["stage"], "define")
        self.assertEqual(session["stage_statuses"]["identify"], "completed")
        self.assertEqual(session["stage_statuses"]["define"], "in_progress")
        self.assertEqual(session["next_stage"], "stress_test")
        self.assertEqual(session["lifecycle_status"], "active")
        self.assertIn("define", session["structured_outputs"])

    def test_generate_deduplicates_only_questions_and_is_idempotent(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        session.define.unresolved_questions = [
            "first",
            "second",
            "first",
            "third",
            "second",
        ]
        session_store.save(session)

        before = session_store.get(UUID(session_id))
        assert before is not None
        soi_before = before.define.soi_candidate.model_copy(deep=True)
        positioning_before = before.define.positioning.model_copy(deep=True)
        values_before = before.define.values.copy()
        moments_before = before.define.moments.copy()
        identify_before = before.structured_outputs["identify"]
        pestle_before = before.identify.output.pestle_findings.copy()

        repaired = orchestrator.initialize_define(UUID(session_id))

        self.assertEqual(
            repaired.unresolved_questions,
            ["first", "second", "third"],
        )
        self.assertEqual(repaired.soi_candidate, soi_before)
        self.assertEqual(repaired.positioning, positioning_before)
        self.assertEqual(repaired.values, values_before)
        self.assertEqual(repaired.moments, moments_before)
        after = session_store.get(UUID(session_id))
        assert after is not None
        self.assertEqual(after.structured_outputs["identify"], identify_before)
        self.assertEqual(after.identify.output.pestle_findings, pestle_before)

        repaired_version = repaired.version
        second = orchestrator.initialize_define(UUID(session_id))
        self.assertEqual(second.unresolved_questions, repaired.unresolved_questions)
        self.assertEqual(second.version, repaired_version)

    def test_generate_repairs_only_missing_soi_and_is_idempotent(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        original = orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        session.define.soi_candidate = None
        session.define.positioning = session.define.positioning.model_copy(
            update={
                "audience": "User-edited audience",
                "approval_status": DefineApprovalStatus.user_edited,
            }
        )
        session.define.values[0] = session.define.values[0].model_copy(
            update={
                "meaning": "User-edited commitment",
                "approval_status": DefineApprovalStatus.user_edited,
            }
        )
        session.define.moments[0] = session.define.moments[0].model_copy(
            update={
                "the_move": "User-edited move",
                "approval_status": DefineApprovalStatus.agreed,
            }
        )
        session.define.unresolved_questions.append("Preserve this question")
        session.define.provenance = session.define.provenance.model_copy(
            update={"status": EvidenceStatus.user_confirmed}
        )
        session_store.save(session)

        before = session_store.get(UUID(session_id))
        assert before is not None
        handoff_before = before.structured_outputs["identify"]["handoff"]
        positioning_before = before.define.positioning.model_copy(deep=True)
        values_before = before.define.values.copy()
        moments_before = before.define.moments.copy()
        questions_before = before.define.unresolved_questions.copy()
        evidence_before = before.define.evidence_references.copy()
        provenance_before = before.define.provenance.model_copy(deep=True)
        coverage_before = before.identify.playbook_coverage.copy()
        pestle_before = before.identify.output.pestle_findings.copy()

        repaired = orchestrator.initialize_define(UUID(session_id))

        self.assertIsNotNone(repaired.soi_candidate)
        assert repaired.soi_candidate is not None
        self.assertTrue(repaired.soi_candidate.statement.strip())
        self.assertEqual(repaired.positioning, positioning_before)
        self.assertEqual(repaired.values, values_before)
        self.assertEqual(repaired.moments, moments_before)
        self.assertEqual(repaired.unresolved_questions, questions_before)
        self.assertEqual(repaired.evidence_references, evidence_before)
        self.assertEqual(repaired.provenance, provenance_before)
        self.assertEqual(repaired.status, original.status)

        after = session_store.get(UUID(session_id))
        assert after is not None
        self.assertEqual(after.structured_outputs["identify"]["handoff"], handoff_before)
        self.assertEqual(after.identify.playbook_coverage, coverage_before)
        self.assertEqual(after.identify.output.pestle_findings, pestle_before)
        self.assertEqual(len(after.identify.playbook_coverage), 20)

        repaired_version = repaired.version
        soi_id = repaired.soi_candidate.id
        second = orchestrator.initialize_define(UUID(session_id))

        assert second.soi_candidate is not None
        self.assertEqual(second.soi_candidate.id, soi_id)
        self.assertEqual(second.version, repaired_version)

    def test_generate_does_not_overwrite_existing_valid_soi(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        generated = orchestrator.initialize_define(UUID(session_id))
        assert generated.soi_candidate is not None
        existing_id = generated.soi_candidate.id
        existing_statement = generated.soi_candidate.statement
        existing_version = generated.version

        returned = orchestrator.initialize_define(UUID(session_id))

        assert returned.soi_candidate is not None
        self.assertEqual(returned.soi_candidate.id, existing_id)
        self.assertEqual(returned.soi_candidate.statement, existing_statement)
        self.assertEqual(returned.version, existing_version)

    def test_generate_repairs_only_ai_proposed_semantically_invalid_soi(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        assert session.define.soi_candidate is not None
        invalid_statement = (
            "Dominant market share and claims ratio signals cost pressure."
        )
        session.define.soi_candidate = session.define.soi_candidate.model_copy(
            update={
                "statement": invalid_statement,
                "guiding_star": invalid_statement,
                "meaning": (
                    "Customers Getting a quote should feel reliable. Getting a "
                    "quote may be a strength to preserve."
                ),
                "approval_status": DefineApprovalStatus.ai_proposed,
            }
        )
        positioning_before = session.define.positioning.model_copy(deep=True)
        values_before = session.define.values.copy()
        moments_before = session.define.moments.copy()
        identify_before = session.structured_outputs["identify"]
        session_store.save(session)

        repaired = orchestrator.initialize_define(UUID(session_id))

        assert repaired.soi_candidate is not None
        self.assertNotEqual(repaired.soi_candidate.statement, invalid_statement)
        self.assertNotIn("Customers Getting", repaired.soi_candidate.meaning)
        self.assertEqual(repaired.positioning, positioning_before)
        self.assertEqual(repaired.values, values_before)
        self.assertEqual(repaired.moments, moments_before)
        saved = session_store.get(UUID(session_id))
        assert saved is not None
        self.assertEqual(saved.structured_outputs["identify"], identify_before)

        repaired_version = repaired.version
        second = orchestrator.initialize_define(UUID(session_id))
        self.assertEqual(second.soi_candidate, repaired.soi_candidate)
        self.assertEqual(second.version, repaired_version)

    def test_generate_preserves_user_edited_and_agreed_invalid_soi(self) -> None:
        for approval_status in (
            DefineApprovalStatus.user_edited,
            DefineApprovalStatus.agreed,
        ):
            with self.subTest(approval_status=approval_status):
                session_store.clear()
                session_id = complete_identify_inputs()
                request("POST", f"/api/sessions/{session_id}/identify/complete")
                orchestrator = PurpOSOrchestrator()
                orchestrator.initialize_define(UUID(session_id))

                session = session_store.get(UUID(session_id))
                assert session is not None
                assert session.define.soi_candidate is not None
                protected = session.define.soi_candidate.model_copy(
                    update={
                        "statement": "Market share and claims ratio analysis.",
                        "approval_status": approval_status,
                    }
                )
                session.define.soi_candidate = protected
                session_store.save(session)
                saved = session_store.get(UUID(session_id))
                assert saved is not None
                saved_version = saved.define.version

                returned = orchestrator.initialize_define(UUID(session_id))

                self.assertEqual(returned.soi_candidate, protected)
                self.assertEqual(returned.version, saved_version)

    def test_generate_repairs_blank_or_whitespace_persisted_soi(self) -> None:
        for invalid_statement in ("", "   "):
            with self.subTest(statement=repr(invalid_statement)):
                session_store.clear()
                session_id = complete_identify_inputs()
                request("POST", f"/api/sessions/{session_id}/identify/complete")
                orchestrator = PurpOSOrchestrator()
                generated = orchestrator.initialize_define(UUID(session_id))
                assert generated.soi_candidate is not None

                session = session_store.get(UUID(session_id))
                assert session is not None
                session.define.soi_candidate = session.define.soi_candidate.model_copy(
                    update={"statement": invalid_statement}
                )
                session_store.save(session)

                repaired = orchestrator.initialize_define(UUID(session_id))

                assert repaired.soi_candidate is not None
                self.assertTrue(repaired.soi_candidate.statement.strip())

    def test_patch_define_positioning_marks_user_edit(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        request("POST", f"/api/sessions/{session_id}/define/generate")

        response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/positioning",
            {
                "audience": "Clinic managers",
                "categoryContext": "operations support",
                "capabilityValue": "keeps appointment flow reliable",
                "reasonBelievability": "customers need daily confidence",
                "composedStatement": (
                    "For clinic managers, Meridian is operations support that "
                    "keeps appointment flow reliable because customers need "
                    "daily confidence."
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        positioning = response.json()["positioning"]
        self.assertEqual(positioning["audience"], "Clinic managers")
        self.assertEqual(positioning["categoryContext"], "operations support")
        self.assertEqual(
            positioning["capabilityValue"],
            "keeps appointment flow reliable",
        )
        self.assertEqual(
            positioning["reasonBelievability"],
            "customers need daily confidence",
        )
        self.assertEqual(positioning["approvalStatus"], "user-edited")
        self.assertEqual(positioning["provenance"]["status"], "user-confirmed")

    def test_positioning_approval_persists_after_reload(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        request("POST", f"/api/sessions/{session_id}/define/generate")
        payload = {
            "audience": "Clinic managers",
            "categoryContext": "operations partner",
            "capabilityValue": "keeps appointment flow reliable",
            "reasonBelievability": "customers need daily confidence",
            "composedStatement": (
                "For Clinic managers, Meridian is the operations partner that "
                "keeps appointment flow reliable - because customers need daily confidence"
            ),
            "approvalStatus": "agreed",
        }

        response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/positioning",
            payload,
        )
        reloaded = request(
            "GET",
            f"/api/sessions/{session_id}/define",
        ).json()["define"]["positioning"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(reloaded["approvalStatus"], "agreed")
        for field in (
            "audience",
            "categoryContext",
            "capabilityValue",
            "reasonBelievability",
            "composedStatement",
        ):
            self.assertEqual(reloaded[field], payload[field])

    def test_generate_repairs_ai_proposed_positioning_and_is_idempotent(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        session.define.positioning = session.define.positioning.model_copy(
            update={
                "audience": None,
                "category_context": None,
                "capability_value": None,
                "reason_believability": None,
                "composed_statement": None,
                "approval_status": DefineApprovalStatus.ai_proposed,
            }
        )
        values_before = session.define.values.copy()
        moments_before = session.define.moments.copy()
        session_store.save(session)

        repaired = orchestrator.initialize_define(UUID(session_id))

        self.assertTrue(repaired.positioning.audience.strip())
        self.assertTrue(repaired.positioning.category_context.strip())
        self.assertTrue(repaired.positioning.capability_value.strip())
        self.assertTrue(repaired.positioning.reason_believability.strip())
        self.assertTrue(repaired.positioning.composed_statement.strip())
        self.assertEqual(repaired.values, values_before)
        self.assertEqual(repaired.moments, moments_before)

        repaired_version = repaired.version
        second = orchestrator.initialize_define(UUID(session_id))
        self.assertEqual(second.positioning, repaired.positioning)
        self.assertEqual(second.version, repaired_version)

    def test_generate_does_not_repair_user_edited_incomplete_positioning(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        session.define.positioning = session.define.positioning.model_copy(
            update={
                "category_context": None,
                "approval_status": DefineApprovalStatus.user_edited,
            }
        )
        session_store.save(session)
        saved = session_store.get(UUID(session_id))
        assert saved is not None
        saved_version = saved.define.version

        returned = orchestrator.initialize_define(UUID(session_id))

        self.assertIsNone(returned.positioning.category_context)
        self.assertEqual(returned.positioning.approval_status, "user-edited")
        self.assertEqual(returned.version, saved_version)

    def test_generate_repairs_role_inappropriate_ai_positioning(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        orchestrator.initialize_define(UUID(session_id))

        market_analysis = (
            "Dominant market share combined with a high claims-to-premium "
            "ratio signals cost pressure."
        )
        session = session_store.get(UUID(session_id))
        assert session is not None
        session.define.positioning = session.define.positioning.model_copy(
            update={
                "audience": "Customers",
                "category_context": market_analysis,
                "capability_value": market_analysis,
                "reason_believability": "Documented service delivery evidence.",
                "composed_statement": "Stale composed statement",
                "approval_status": DefineApprovalStatus.ai_proposed,
            }
        )
        session_store.save(session)

        repaired = orchestrator.initialize_define(UUID(session_id))

        self.assertEqual(repaired.positioning.audience, "Customers")
        self.assertNotEqual(repaired.positioning.category_context, market_analysis)
        self.assertNotEqual(repaired.positioning.capability_value, market_analysis)
        self.assertEqual(
            repaired.positioning.reason_believability,
            "Documented service delivery evidence.",
        )
        self.assertNotEqual(
            repaired.positioning.composed_statement,
            "Stale composed statement",
        )

    def test_generate_does_not_repair_agreed_positioning(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        generated = orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        agreed = generated.positioning.model_copy(
            update={
                "category_context": (
                    "Dominant market share and claims ratio analysis."
                ),
                "approval_status": DefineApprovalStatus.agreed,
            }
        )
        session.define.positioning = agreed
        session_store.save(session)
        saved = session_store.get(UUID(session_id))
        assert saved is not None
        saved_version = saved.define.version

        returned = orchestrator.initialize_define(UUID(session_id))

        self.assertEqual(returned.positioning, agreed)
        self.assertEqual(returned.version, saved_version)

    def test_generate_repairs_only_ai_value_meanings_and_is_idempotent(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        original = orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        original_value = session.define.values[0]
        session.define.values[0] = original_value.model_copy(
            update={
                "meaning": None,
                "approval_status": DefineApprovalStatus.ai_proposed,
            }
        )
        if len(session.define.values) > 1:
            session.define.values[1] = session.define.values[1].model_copy(
                update={
                    "meaning": None,
                    "approval_status": DefineApprovalStatus.user_edited,
                }
            )
        protected_value = (
            session.define.values[1].model_copy(deep=True)
            if len(session.define.values) > 1
            else None
        )
        soi_before = session.define.soi_candidate.model_copy(deep=True)
        positioning_before = session.define.positioning.model_copy(deep=True)
        moments_before = session.define.moments.copy()
        identify_before = session.structured_outputs["identify"]["handoff"]
        pestle_before = session.identify.output.pestle_findings.copy()
        coverage_before = session.identify.playbook_coverage.copy()
        session_store.save(session)

        repaired = orchestrator.initialize_define(UUID(session_id))

        self.assertEqual(repaired.values[0].id, original_value.id)
        self.assertEqual(repaired.values[0].name, original_value.name)
        self.assertTrue(repaired.values[0].meaning.strip())
        if protected_value is not None:
            self.assertEqual(repaired.values[1], protected_value)
        self.assertEqual(repaired.soi_candidate, soi_before)
        self.assertEqual(repaired.positioning, positioning_before)
        self.assertEqual(repaired.moments, moments_before)

        persisted = session_store.get(UUID(session_id))
        assert persisted is not None
        self.assertEqual(
            persisted.structured_outputs["identify"]["handoff"],
            identify_before,
        )
        self.assertEqual(persisted.identify.output.pestle_findings, pestle_before)
        self.assertEqual(persisted.identify.playbook_coverage, coverage_before)
        self.assertEqual(len(persisted.identify.playbook_coverage), 20)

        repaired_version = repaired.version
        second = orchestrator.initialize_define(UUID(session_id))
        self.assertEqual(second.values, repaired.values)
        self.assertEqual(second.version, repaired_version)

    def test_generate_repairs_sparse_ai_moment_and_is_idempotent(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        orchestrator = PurpOSOrchestrator()
        generated = orchestrator.initialize_define(UUID(session_id))

        session = session_store.get(UUID(session_id))
        assert session is not None
        original_moment = generated.moments[0]
        session.define.moments[0] = original_moment.model_copy(
            update={
                "question": None,
                "today": None,
                "desired_state": None,
                "the_move": None,
                "supporting_evidence": [],
                "status": "gap-to-close",
                "approval_status": DefineApprovalStatus.ai_proposed,
            }
        )
        if len(session.define.moments) > 1:
            session.define.moments[1] = session.define.moments[1].model_copy(
                update={
                    "question": None,
                    "approval_status": DefineApprovalStatus.user_edited,
                }
            )
        protected_moment = (
            session.define.moments[1].model_copy(deep=True)
            if len(session.define.moments) > 1
            else None
        )
        soi_before = session.define.soi_candidate.model_copy(deep=True)
        positioning_before = session.define.positioning.model_copy(deep=True)
        values_before = session.define.values.copy()
        identify_before = session.structured_outputs["identify"]["handoff"]
        pestle_before = session.identify.output.pestle_findings.copy()
        session_store.save(session)

        repaired = orchestrator.initialize_define(UUID(session_id))

        self.assertEqual(repaired.moments[0].id, original_moment.id)
        self.assertEqual(repaired.moments[0].name, original_moment.name)
        self.assertEqual(repaired.moments[0].question, original_moment.question)
        self.assertEqual(repaired.moments[0].today, original_moment.today)
        self.assertEqual(
            repaired.moments[0].desired_state,
            original_moment.desired_state,
        )
        self.assertEqual(repaired.moments[0].the_move, original_moment.the_move)
        self.assertEqual(repaired.moments[0].status, original_moment.status)
        if protected_moment is not None:
            self.assertEqual(repaired.moments[1], protected_moment)
        self.assertEqual(repaired.soi_candidate, soi_before)
        self.assertEqual(repaired.positioning, positioning_before)
        self.assertEqual(repaired.values, values_before)

        persisted = session_store.get(UUID(session_id))
        assert persisted is not None
        self.assertEqual(
            persisted.structured_outputs["identify"]["handoff"],
            identify_before,
        )
        self.assertEqual(persisted.identify.output.pestle_findings, pestle_before)

        repaired_version = repaired.version
        second = orchestrator.initialize_define(UUID(session_id))
        self.assertEqual(second.moments, repaired.moments)
        self.assertEqual(second.version, repaired_version)

    def test_patch_define_value_and_moment_validate_ids(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        define = request(
            "POST",
            f"/api/sessions/{session_id}/define/generate",
        ).json()["define"]

        value_id = define["values"][0]["id"]
        value_response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/values/{value_id}",
            {"meaning": "A commitment the team has explicitly agreed.", "approvalStatus": "agreed"},
        )
        self.assertEqual(value_response.status_code, 200)
        self.assertEqual(value_response.json()["value"]["approvalStatus"], "agreed")

        moment_id = define["moments"][0]["id"]
        moment_response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/moments/{moment_id}",
            {"status": "gap-to-close", "theMove": "Clarify the next operating move."},
        )
        self.assertEqual(moment_response.status_code, 200)
        self.assertEqual(moment_response.json()["moment"]["status"], "gap-to-close")

        missing_response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/moments/{uuid4()}",
            {"status": "on-course"},
        )
        self.assertEqual(missing_response.status_code, 404)

    def test_patch_define_moment_persists_full_detail_and_preserves_evidence(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        define = request(
            "POST",
            f"/api/sessions/{session_id}/define/generate",
        ).json()["define"]
        original = define["moments"][0]

        response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/moments/{original['id']}",
            {
                "name": "Reliable onboarding",
                "question": "How should a new customer experience onboarding?",
                "today": "Handoffs vary by team.",
                "desiredState": "Every customer gets a clear, consistent start.",
                "theMove": "Adopt one shared onboarding sequence.",
                "status": "gap-to-close",
                "approvalStatus": "agreed",
            },
        )

        self.assertEqual(response.status_code, 200)
        saved = response.json()["moment"]
        self.assertEqual(saved["id"], original["id"])
        self.assertEqual(saved["today"], "Handoffs vary by team.")
        self.assertEqual(
            saved["desiredState"],
            "Every customer gets a clear, consistent start.",
        )
        self.assertEqual(saved["theMove"], "Adopt one shared onboarding sequence.")
        self.assertEqual(saved["status"], "gap-to-close")
        self.assertEqual(saved["approvalStatus"], "agreed")
        self.assertEqual(saved["evidenceIds"], original["evidenceIds"])
        self.assertEqual(saved["supportingEvidence"], original["supportingEvidence"])
        self.assertEqual(saved["provenance"]["status"], "user-confirmed")
        self.assertEqual(
            saved["provenance"]["sourceHandoff"],
            "structured_outputs.identify.handoff",
        )

        reloaded = request("GET", f"/api/sessions/{session_id}/define").json()["define"]
        reloaded_moment = next(
            item for item in reloaded["moments"] if item["id"] == original["id"]
        )
        self.assertEqual(reloaded_moment, saved)
        self.assertIn(
            original["id"],
            [item["id"] for item in reloaded["output"]["agreedMoments"]],
        )


if __name__ == "__main__":
    unittest.main()
