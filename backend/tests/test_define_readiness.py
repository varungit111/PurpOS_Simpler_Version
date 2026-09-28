import unittest
from uuid import UUID

from app.orchestrator.orchestrator import (
    DefineEntryBlockedError,
    PurpOSOrchestrator,
)
from app.schemas.assessment import (
    CompanyCardsEvidence,
    DefineApprovalStatus,
    ResearchFinding,
    ResearchSourceType,
)
from app.services.define_evidence import get_define_evidence_ids
from app.services.define_readiness import evaluate_define_readiness
from app.store.sessions import session_store
from backend.tests.test_identify_brief_api import complete_identify_inputs, request


class DefineReadinessTests(unittest.TestCase):
    RESEARCH_ONE_ID = UUID("10a2b9aa-06ce-4d23-b374-49ecafb2e390")
    RESEARCH_TWO_ID = UUID("4bec1cf1-5066-492b-85fd-35565f43d7e8")
    COMPANY_CARDS_ID = UUID("79951f7f-2497-4c6c-9c95-47516e634935")
    UNKNOWN_ID = UUID("8a2b9aa6-1e3e-4a36-9d09-c5c40905201a")

    def setUp(self) -> None:
        session_store.clear()
        session_id = complete_identify_inputs()
        self.session_id = UUID(session_id)
        session = session_store.get(self.session_id)
        assert session is not None
        session.identify.output.research_findings = [
            ResearchFinding(
                id=self.RESEARCH_ONE_ID,
                topic="Organisation Structure and Business Model",
                summary="The organisation has a documented operating model.",
                sourceType=ResearchSourceType.public_website,
                sourceLabel="Organisation website",
            ),
            ResearchFinding(
                id=self.RESEARCH_TWO_ID,
                topic="Products, Digital Tools, and Member Services",
                summary="The organisation provides documented member services.",
                sourceType=ResearchSourceType.public_website,
                sourceLabel="Organisation website",
            ),
        ]
        session.identify.output.company_cards_evidence = CompanyCardsEvidence(
            id=self.COMPANY_CARDS_ID,
            explanation="The selected cards document the organisation's identity.",
        )
        session_store.save(session)
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        self.orchestrator = PurpOSOrchestrator()
        self.orchestrator.initialize_define(self.session_id)

    def test_research_and_company_cards_share_edit_and_readiness_contract(self) -> None:
        session = self._ready_session()
        expected = {
            self.RESEARCH_ONE_ID,
            self.RESEARCH_TWO_ID,
            self.COMPANY_CARDS_ID,
        }
        session.define.evidence_references = sorted(expected, key=str)

        self.assertTrue(expected.issubset(get_define_evidence_ids(session)))
        self.orchestrator._validate_define_evidence_ids(
            self.session_id,
            list(expected),
        )
        readiness = evaluate_define_readiness(session)

        self.assertTrue(readiness.can_complete)
        self.assertFalse(readiness.blocking_issues)

    def test_unknown_evidence_is_rejected_by_edit_and_readiness(self) -> None:
        session = self._ready_session()
        session.define.evidence_references = [self.UNKNOWN_ID]

        with self.assertRaises(DefineEntryBlockedError):
            self.orchestrator._validate_define_evidence_ids(
                self.session_id,
                [self.UNKNOWN_ID],
            )
        readiness = evaluate_define_readiness(session)

        self.assertFalse(readiness.can_complete)
        invalid = [
            issue
            for issue in readiness.blocking_issues
            if issue.code == "invalid-evidence"
        ]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0].evidence_ids, [self.UNKNOWN_ID])

    def test_human_review_requirements_remain_enforced(self) -> None:
        session = self._ready_session()
        session.define.evidence_references = [self.RESEARCH_ONE_ID]
        session.define.values = [
            value.model_copy(
                update={"approval_status": DefineApprovalStatus.ai_proposed}
            )
            for value in session.define.values
        ]

        readiness = evaluate_define_readiness(session)

        self.assertFalse(readiness.can_complete)
        self.assertIn(
            "agreed-values",
            [issue.code for issue in readiness.blocking_issues],
        )

    def test_known_question_keys_are_presented_without_changing_storage(self) -> None:
        session = self._ready_session()
        session.define.evidence_references = [self.RESEARCH_ONE_ID]
        session.define.unresolved_questions = [
            "pestle_findings",
            "A distinct question?",
        ]

        readiness = evaluate_define_readiness(session)

        self.assertEqual(
            readiness.open_questions,
            ["Review relevant PESTLE findings.", "A distinct question?"],
        )
        self.assertEqual(
            session.define.unresolved_questions,
            ["pestle_findings", "A distinct question?"],
        )

    def _ready_session(self):
        session = session_store.get(self.session_id)
        assert session is not None
        assert session.define.soi_candidate is not None
        session.define.soi_candidate = session.define.soi_candidate.model_copy(
            update={"approval_status": DefineApprovalStatus.agreed}
        )
        session.define.positioning = session.define.positioning.model_copy(
            update={"approval_status": DefineApprovalStatus.agreed}
        )
        session.define.values = [
            value.model_copy(update={"approval_status": DefineApprovalStatus.agreed})
            for value in session.define.values
        ]
        session.define.moments = [
            moment.model_copy(update={"approval_status": DefineApprovalStatus.agreed})
            for moment in session.define.moments
        ]
        return session


if __name__ == "__main__":
    unittest.main()
