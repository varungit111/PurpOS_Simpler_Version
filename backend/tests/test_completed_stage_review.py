import unittest
from uuid import UUID

from app.schemas.assessment import (
    AssessmentLifecycleStatus,
    AssessmentStage,
    AssessmentStageStatus,
    IdentifyCompletionStatus,
)
from app.store.sessions import session_store
from backend.tests.test_identify_brief_api import request
from backend.tests.test_stakeholders_api import stakeholder_payload
from backend.tests.test_stress_test_api import ready_define


class CompletedStageReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_active_identify_remains_editable(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )

        self.assertEqual(response.status_code, 200)

    def test_completed_identify_is_readable_but_rejects_mutation(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        session_id = UUID(str(created["id"]))
        request(
            "PUT",
            f"/api/sessions/{session_id}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )
        session = session_store.get(session_id)
        assert session is not None
        session.identify.completion_status = IdentifyCompletionStatus.completed
        session.stage = AssessmentStage.stress_test
        session.lifecycle_status = AssessmentLifecycleStatus.active
        session.stage_statuses[AssessmentStage.identify] = (
            AssessmentStageStatus.completed
        )
        session.stage_statuses[AssessmentStage.define] = AssessmentStageStatus.completed
        session.stage_statuses[AssessmentStage.stress_test] = (
            AssessmentStageStatus.in_progress
        )
        session_store.save(session)

        before = session_store.get(session_id)
        assert before is not None
        before_evidence = before.identify.model_copy(deep=True)

        read_response = request(
            "GET", f"/api/sessions/{session_id}/identify/stakeholders"
        )
        mutation_response = request(
            "PUT",
            f"/api/sessions/{session_id}/identify/stakeholders",
            {"stakeholders": []},
        )
        completion_response = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(mutation_response.status_code, 409)
        self.assertEqual(completion_response.status_code, 409)
        after = session_store.get(session_id)
        assert after is not None
        self.assertEqual(after.version, before.version)
        self.assertEqual(after.identify, before_evidence)
        self.assertEqual(after.stage, AssessmentStage.stress_test)
        self.assertEqual(after.lifecycle_status, AssessmentLifecycleStatus.active)

    def test_completed_define_rejects_generation_and_edits_without_changes(self) -> None:
        session_id_value, _ = ready_define()
        request("POST", f"/api/sessions/{session_id_value}/define/complete")
        session_id = UUID(session_id_value)
        before = session_store.get(session_id)
        assert before is not None
        before_define = before.define.model_copy(deep=True)

        generate_response = request(
            "POST", f"/api/sessions/{session_id}/define/generate"
        )
        mutation_response = request(
            "PATCH",
            f"/api/sessions/{session_id}/define/positioning",
            {
                "audience": "Changed after progression",
                "approvalStatus": "user-edited",
            },
        )

        self.assertEqual(generate_response.status_code, 409)
        self.assertEqual(mutation_response.status_code, 409)
        after = session_store.get(session_id)
        assert after is not None
        self.assertEqual(after.version, before.version)
        self.assertEqual(after.define, before_define)
        self.assertEqual(after.stage, AssessmentStage.stress_test)
        self.assertEqual(after.lifecycle_status, AssessmentLifecycleStatus.active)


if __name__ == "__main__":
    unittest.main()
