import unittest
from backend.tests.test_identify_brief_api import complete_identify_inputs, request
from app.services.stress_test import STRESS_TEST_CRITERIA, OVERARCHING_QUESTION
from app.services.stress_test import evaluate_stress_test
from app.schemas.assessment import DefineOutput
from uuid import uuid4
from app.store.sessions import session_store


def ready_define() -> tuple[str, dict]:
    session_id = complete_identify_inputs()
    request("POST", f"/api/sessions/{session_id}/identify/complete")
    define = request("POST", f"/api/sessions/{session_id}/define/generate").json()["define"]
    request("PATCH", f"/api/sessions/{session_id}/define/soi", {"approvalStatus": "agreed"})
    request("PATCH", f"/api/sessions/{session_id}/define/positioning", {
        "audience": "Clinic managers", "categoryContext": "operations partner",
        "capabilityValue": "makes care workflows reliable", "reasonBelievability": "reliable care benefits customers and communities",
        "composedStatement": "For clinic managers, Meridian is the operations partner that makes care workflows reliable.", "approvalStatus": "agreed",
    })
    request("PATCH", f"/api/sessions/{session_id}/define/values/{define['values'][0]['id']}", {"approvalStatus": "agreed"})
    request("PATCH", f"/api/sessions/{session_id}/define/moments/{define['moments'][0]['id']}", {"approvalStatus": "agreed"})
    return session_id, define


class StressTestEndpointTests(unittest.TestCase):
    def setUp(self) -> None: session_store.clear()

    def test_incomplete_define_is_rejected(self) -> None:
        session_id = complete_identify_inputs()
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        request("POST", f"/api/sessions/{session_id}/define/generate")
        response = request("POST", f"/api/sessions/{session_id}/define/complete")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()["detail"]["canComplete"])

    def test_define_completion_creates_canonical_output_and_eight_criteria(self) -> None:
        session_id, _ = ready_define()
        response = request("POST", f"/api/sessions/{session_id}/define/complete")
        self.assertEqual(response.status_code, 200)
        output = response.json()["output"]
        self.assertEqual(output["completionStatus"], "completed")
        self.assertTrue(output["completedAt"])
        self.assertTrue(output["evidenceReferences"])
        self.assertIn("unresolvedQuestions", output)

        stress = request("GET", f"/api/sessions/{session_id}/stress-test").json()["stressTest"]
        self.assertEqual(len(stress["criteria"]), 8)
        self.assertEqual([item["name"] for item in stress["criteria"]], [item[1] for item in STRESS_TEST_CRITERIA])
        self.assertEqual([item["question"] for item in stress["criteria"]], [item[2] for item in STRESS_TEST_CRITERIA])
        self.assertEqual(stress["overarchingQuestion"], OVERARCHING_QUESTION)
        self.assertNotIn("score", stress)
        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(session["stage"], "stress_test")
        self.assertEqual(session["stage_statuses"]["define"], "completed")

    def test_human_review_is_required_and_completion_makes_alignment_ready(self) -> None:
        session_id, _ = ready_define()
        request("POST", f"/api/sessions/{session_id}/define/complete")
        blocked = request("POST", f"/api/sessions/{session_id}/stress-test/complete")
        self.assertEqual(blocked.status_code, 409)
        stress = request("GET", f"/api/sessions/{session_id}/stress-test").json()["stressTest"]
        evidence = stress["evidenceReferences"]
        for criterion in stress["criteria"]:
            response = request("PATCH", f"/api/sessions/{session_id}/stress-test/criteria/{criterion['criterionId']}", {
                "status": "needs-review", "reasoning": "Reviewed against the agreed Define output.",
                "supportingEvidenceIds": evidence, "concerns": ["Carry this question into Alignment."],
                "suggestedRefinement": "Keep testing this through implementation.", "approvalStatus": "agreed",
            })
            self.assertEqual(response.status_code, 200)
        request("PATCH", f"/api/sessions/{session_id}/stress-test/review", {"overarchingResponse": "Yes, with the recorded concerns carried into Alignment."})
        completed = request("POST", f"/api/sessions/{session_id}/stress-test/complete")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["stressTest"]["status"], "completed")
        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(session["stage"], "stress_test")
        self.assertEqual(session["stage_statuses"]["stress_test"], "completed")
        self.assertEqual(session["stage_statuses"]["align"], "not_started")
        self.assertEqual(session["next_stage"], "align")

    def test_invalid_criterion_is_rejected(self) -> None:
        session_id, _ = ready_define()
        request("POST", f"/api/sessions/{session_id}/define/complete")
        response = request("PATCH", f"/api/sessions/{session_id}/stress-test/criteria/not-real", {"reasoning": "No."})
        self.assertEqual(response.status_code, 404)

    def test_insufficient_evidence_is_explicit_and_never_scored(self) -> None:
        state = evaluate_stress_test(uuid4(), DefineOutput())
        self.assertEqual(len(state.criteria), 8)
        self.assertTrue(all(item.status == "insufficient-evidence" for item in state.criteria))
        self.assertTrue(all(item.concerns for item in state.criteria))
        self.assertFalse(hasattr(state, "score"))


if __name__ == "__main__": unittest.main()
