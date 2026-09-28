import unittest
from uuid import UUID, uuid4

from backend.tests.test_identify_brief_api import request
from backend.tests.test_stress_test_api import ready_define
from app.schemas.assessment import (
    AlignmentOutput,
    AssessmentStage,
    AssessmentStageStatus,
    DefineOutput,
    DecisionCanvas,
    StressTestStatus,
)
from app.services.alignment import (
    AlignmentProposal,
    DecisionReframeProposal,
    initialize_alignment,
    reframe_decision,
)
from app.services.stress_test import build_stress_test_output, evaluate_stress_test
from app.stages.registry import get_stage_config
from app.store.sessions import session_store


def completed_stress_test() -> str:
    session_id, _ = ready_define()
    request("POST", f"/api/sessions/{session_id}/define/complete")
    stress = request("GET", f"/api/sessions/{session_id}/stress-test").json()["stressTest"]
    evidence = stress["evidenceReferences"]
    for criterion in stress["criteria"]:
        request(
            "PATCH",
            f"/api/sessions/{session_id}/stress-test/criteria/{criterion['criterionId']}",
            {
                "status": "needs-review",
                "reasoning": "Reviewed against the agreed purpose framework.",
                "supportingEvidenceIds": evidence,
                "concerns": ["Confirm this decision in implementation."],
                "approvalStatus": "agreed",
            },
        )
    request(
        "PATCH",
        f"/api/sessions/{session_id}/stress-test/review",
        {"overarchingResponse": "Proceed with the reviewed tensions visible."},
    )
    response = request("POST", f"/api/sessions/{session_id}/stress-test/complete")
    assert response.status_code == 200
    return session_id


class FakeAlignmentAIClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(self, prompt, output_schema, system=None):
        self.calls += 1
        return AlignmentProposal()


class FakeReframeAIClient(FakeAlignmentAIClient):
    def generate_structured(self, prompt, output_schema, system=None):
        self.calls += 1
        return DecisionReframeProposal(
            reframedQuestion="How might this choice strengthen the agreed SOI?",
            reasoning="Keeps the choice open while testing strategic alignment.",
        )


class AlignmentEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_cannot_start_before_stress_test_completion(self) -> None:
        session_id, _ = ready_define()
        request("POST", f"/api/sessions/{session_id}/define/complete")

        response = request("POST", f"/api/sessions/{session_id}/align/generate")

        self.assertEqual(response.status_code, 409)
        self.assertIn("completed StressTestOutput", response.json()["detail"])

    def test_cannot_start_without_define_output(self) -> None:
        session_id = completed_stress_test()
        session = session_store.get(UUID(session_id))
        assert session is not None
        session.define.output = None
        session_store.save(session)

        response = request("POST", f"/api/sessions/{session_id}/align/generate")

        self.assertEqual(response.status_code, 409)
        self.assertIn("DefineOutput", response.json()["detail"])

    def test_cannot_start_without_stress_test_output(self) -> None:
        session_id = completed_stress_test()
        session = session_store.get(UUID(session_id))
        assert session is not None
        session.stress_test.output = None
        session_store.save(session)

        response = request("POST", f"/api/sessions/{session_id}/align/generate")

        self.assertEqual(response.status_code, 409)
        self.assertIn("StressTestOutput", response.json()["detail"])

    def test_initialization_transitions_lifecycle_and_has_no_scores(self) -> None:
        session_id = completed_stress_test()

        response = request("POST", f"/api/sessions/{session_id}/align/generate")

        self.assertEqual(response.status_code, 200)
        alignment = response.json()["alignment"]
        self.assertEqual(alignment["status"], "in_progress")
        self.assertTrue(alignment["functionalAlignment"])
        self.assertTrue(alignment["progressSnapshots"])
        self.assertNotIn("score", str(alignment).lower())
        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(session["stage"], "align")
        self.assertEqual(session["stage_statuses"]["stress_test"], "completed")
        self.assertEqual(session["stage_statuses"]["align"], "in_progress")
        self.assertIsNone(session["next_stage"])

    def test_multiple_decisions_preserve_original_and_invalid_id_is_rejected(self) -> None:
        session_id = completed_stress_test()
        request("POST", f"/api/sessions/{session_id}/align/generate")
        first = request("POST", f"/api/sessions/{session_id}/align/decisions", {"question": "Should we enter a new market?"}).json()["decision"]
        second = request("POST", f"/api/sessions/{session_id}/align/decisions", {"question": "Should we change our service model?"}).json()["decision"]

        reframed = request("POST", f"/api/sessions/{session_id}/align/decisions/{first['id']}/reframe").json()["decision"]

        self.assertEqual(reframed["originalQuestion"], "Should we enter a new market?")
        self.assertTrue(reframed["reframedQuestion"])
        state = request("GET", f"/api/sessions/{session_id}/align").json()["alignment"]
        self.assertEqual([item["id"] for item in state["decisions"]], [first["id"], second["id"]])
        invalid = request("POST", f"/api/sessions/{session_id}/align/decisions/{uuid4()}/reframe")
        self.assertEqual(invalid.status_code, 404)

    def test_value_gates_use_real_framework_and_moves_require_adoption(self) -> None:
        session_id = completed_stress_test()
        request("POST", f"/api/sessions/{session_id}/align/generate")
        decision = request("POST", f"/api/sessions/{session_id}/align/decisions", {"question": "Should we acquire a supplier?"}).json()["decision"]

        evaluated = request("POST", f"/api/sessions/{session_id}/align/decisions/{decision['id']}/evaluate").json()["decision"]

        references = [gate["frameworkReference"] for gate in evaluated["valueGates"]]
        self.assertIn("define.soi", references)
        self.assertTrue(any(item.startswith("define.values.") for item in references))
        self.assertTrue(any(item.startswith("stress_test.criteria.") for item in references))
        self.assertTrue(evaluated["suggestedMoves"])
        self.assertTrue(all(not item["adopted"] for item in evaluated["suggestedMoves"]))
        self.assertNotIn("score", str(evaluated).lower())

        move = evaluated["suggestedMoves"][0]
        adopted = request("PATCH", f"/api/sessions/{session_id}/align/moves/{move['id']}", {"adopted": True}).json()["move"]
        self.assertTrue(adopted["adopted"])
        saved = request("GET", f"/api/sessions/{session_id}/align").json()["alignment"]
        self.assertEqual(saved["adoptedActions"][0]["sourceMoveId"], move["id"])
        invalid = request("PATCH", f"/api/sessions/{session_id}/align/moves/{uuid4()}", {"adopted": True})
        self.assertEqual(invalid.status_code, 404)

    def test_progress_is_structured_without_percentages(self) -> None:
        session_id = completed_stress_test()
        request("POST", f"/api/sessions/{session_id}/align/generate")

        payload = request("GET", f"/api/sessions/{session_id}/align/progress").json()

        self.assertTrue(payload["snapshots"])
        self.assertIn("outstandingActionIds", payload["snapshots"][0])
        self.assertNotIn("percentage", str(payload).lower())

    def test_shared_ai_client_is_used_and_output_is_validated(self) -> None:
        define = DefineOutput()
        stress = evaluate_stress_test(uuid4(), define)
        stress.status = StressTestStatus.completed
        stress.output = build_stress_test_output(stress)
        fake = FakeAlignmentAIClient()

        state = initialize_alignment(uuid4(), define, stress.output, fake)

        self.assertEqual(fake.calls, 1)
        self.assertIsInstance(state.output, AlignmentOutput)

    def test_mocked_ai_reframe_preserves_original_question(self) -> None:
        define = DefineOutput()
        stress_state = evaluate_stress_test(uuid4(), define)
        stress_output = build_stress_test_output(stress_state)
        decision = DecisionCanvas(originalQuestion="Should we change suppliers?")
        fake = FakeReframeAIClient()

        reframed = reframe_decision(decision, define, stress_output, fake)

        self.assertEqual(fake.calls, 1)
        self.assertEqual(reframed.original_question, "Should we change suppliers?")
        self.assertEqual(reframed.reframed_question, "How might this choice strengthen the agreed SOI?")

    def test_alignment_stage_config_is_registered(self) -> None:
        config = get_stage_config(AssessmentStage.align)

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.output_schema, "AlignmentOutput")
        self.assertIn("shared_ai_client", config.available_tools)


if __name__ == "__main__":
    unittest.main()
