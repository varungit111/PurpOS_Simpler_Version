import unittest
from uuid import uuid4

from app.orchestrator.orchestrator import (
    DefineEntryBlockedError,
    InvalidStageTransitionError,
    PurpOSOrchestrator,
    SessionNotFoundError,
)
from app.schemas.assessment import (
    AssessmentSessionCreate,
    AssessmentStage,
    Stakeholder,
)
from app.schemas.conversation import (
    AIConversationRecommendation,
    ConversationAction,
)
from app.services.ai_client import AIMessage
from app.store.sessions import session_store


class FakeAIClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return prompt

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIConversationRecommendation],
        system: str | None = None,
    ) -> AIConversationRecommendation:
        self.calls += 1
        return output_schema(
            recommended_action=ConversationAction.ask_question,
            next_question="What evidence shows customers experience this?",
        )

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        return messages[-1].content


class PurpOSOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()
        self.orchestrator = PurpOSOrchestrator()

    def test_start_assessment_creates_valid_identify_state(self) -> None:
        state = self.orchestrator.start_assessment()

        self.assertEqual(state.current_stage, AssessmentStage.identify)
        self.assertEqual(state.stage_config.stage, AssessmentStage.identify)
        self.assertEqual(state.context.stage, AssessmentStage.identify)
        self.assertEqual(state.lifecycle_status, "active")

    def test_get_state_bootstraps_existing_session_state(self) -> None:
        session = session_store.create(
            AssessmentSessionCreate(stage=AssessmentStage.identify)
        )

        state = self.orchestrator.get_state(session.id)

        self.assertEqual(state.session_id, session.id)
        self.assertEqual(state.current_stage, AssessmentStage.identify)

    def test_get_state_bootstraps_saved_stakeholder_map_context(self) -> None:
        session = session_store.create(
            AssessmentSessionCreate(stage=AssessmentStage.identify)
        )
        session_store.update_identify_stakeholders(
            session.id,
            [
                Stakeholder(
                    name="Clinic managers",
                    groupType="customer",
                    internalOrExternal="external",
                    relationship="Primary buyer and daily sponsor",
                    importance="high",
                    influence="medium",
                    needs=["Reliable appointment flow"],
                    expectations=["Fast support"],
                    evidenceSource="Who Matters?",
                )
            ],
        )

        state = self.orchestrator.get_state(session.id)

        self.assertEqual(
            state.context.collected_fields["stakeholder_insights"],
            "Stakeholder map captured through Who Matters.",
        )
        self.assertIn("customer_needs", state.context.covered_question_area_ids)

    def test_get_state_refreshes_cached_stakeholder_map_context(self) -> None:
        state = self.orchestrator.start_assessment()
        session_store.update_identify_stakeholders(
            state.session_id,
            [
                Stakeholder(
                    name="Clinic managers",
                    groupType="customer",
                    internalOrExternal="external",
                    importance="high",
                    influence="medium",
                    evidenceSource="Who Matters?",
                )
            ],
        )

        refreshed = self.orchestrator.get_state(state.session_id)

        self.assertEqual(
            refreshed.context.collected_fields["stakeholder_insights"],
            "Stakeholder map captured through Who Matters.",
        )

    def test_handle_message_delegates_processing_and_stores_output(self) -> None:
        state = self.orchestrator.start_assessment()

        result = self.orchestrator.handle_message(
            state.session_id,
            "We build scheduling software for regional clinics.",
        )

        self.assertEqual(result.state.session_id, state.session_id)
        self.assertEqual(
            result.conversation_result.action, ConversationAction.ask_question
        )
        outputs = self.orchestrator.get_structured_outputs(state.session_id)
        self.assertIn("identify", outputs)
        self.assertIn("discovery_brief", outputs["identify"])

    def test_new_orchestrator_resumes_saved_context_and_outputs(self) -> None:
        state = self.orchestrator.start_assessment()
        self.orchestrator.handle_message(
            state.session_id,
            "We build scheduling software for regional clinics.",
        )

        resumed = PurpOSOrchestrator().get_state(state.session_id)

        self.assertEqual(resumed.current_stage, AssessmentStage.identify)
        self.assertEqual(
            resumed.context.collected_fields["discovery_brief"],
            "We build scheduling software for regional clinics.",
        )
        self.assertIn(AssessmentStage.identify, resumed.structured_outputs)
        self.assertEqual(resumed.context.turns, [])

    def test_handle_message_passes_injected_ai_client_to_engine(self) -> None:
        ai_client = FakeAIClient()
        orchestrator = PurpOSOrchestrator(ai_client=ai_client)
        state = orchestrator.start_assessment()

        result = orchestrator.handle_message(
            state.session_id,
            "We build scheduling software for regional clinics.",
        )

        self.assertEqual(ai_client.calls, 1)
        self.assertEqual(
            result.conversation_result.next_question,
            "What evidence shows customers experience this?",
        )

    def test_revisit_routing_records_explicit_topic_route(self) -> None:
        state = self.orchestrator.start_assessment()

        updated = self.orchestrator.revisit_topic(
            state.session_id,
            topic="positioning",
            reason="Needs clearer customer evidence.",
        )

        self.assertEqual(updated.revisit_routes[-1].topic, "positioning")
        self.assertEqual(
            updated.revisit_routes[-1].reason,
            "Needs clearer customer evidence.",
        )

    def test_incomplete_identify_stage_cannot_complete(self) -> None:
        state = self.orchestrator.start_assessment()

        from app.orchestrator.orchestrator import IdentifyCompletionBlockedError

        with self.assertRaises(IdentifyCompletionBlockedError):
            self.orchestrator.complete_stage(state.session_id)

    def test_handle_message_records_engine_requested_revisit(self) -> None:
        state = self.orchestrator.start_assessment()

        result = self.orchestrator.handle_message(
            state.session_id, "Purpose matters."
        )

        self.assertEqual(
            result.conversation_result.action, ConversationAction.revisit_topic
        )
        self.assertEqual(
            result.state.revisit_routes[-1].topic, "social_contribution"
        )

    def test_rejects_out_of_order_stage_transition(self) -> None:
        state = self.orchestrator.start_assessment()

        with self.assertRaises(InvalidStageTransitionError):
            self.orchestrator.advance_stage(state.session_id, AssessmentStage.align)

    def test_rejects_define_transition_before_identify_completion(self) -> None:
        state = self.orchestrator.start_assessment()

        with self.assertRaises(DefineEntryBlockedError):
            self.orchestrator.advance_stage(state.session_id)

    def test_session_not_found_raises_domain_error(self) -> None:
        with self.assertRaises(SessionNotFoundError):
            self.orchestrator.get_state(uuid4())


if __name__ == "__main__":
    unittest.main()
