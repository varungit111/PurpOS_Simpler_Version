import unittest

from app.conversation.engine import ConversationEngine
from app.schemas.assessment import (
    EvidenceSource,
    IdentifyEvidence,
    PlaybookCoverageStatus,
)
from app.schemas.conversation import (
    AIConversationRecommendation,
    ConversationAction,
    ConversationRole,
    ConversationTurn,
    CrossCheckIssueType,
    StructuredEvidenceUpdate,
)
from app.services.ai_client import AIClientError, AIMessage
from app.stages.identify import identify_stage_config


class FakeAIClient:
    def __init__(self, recommendation: AIConversationRecommendation) -> None:
        self.recommendation = recommendation
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return prompt

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIConversationRecommendation],
        system: str | None = None,
    ) -> AIConversationRecommendation:
        self.prompts.append(prompt)
        return output_schema.model_validate(self.recommendation)

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        return messages[-1].content


class FailingAIClient:
    def generate_text(self, prompt: str, system: str | None = None) -> str:
        raise AIClientError("AI unavailable.")

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIConversationRecommendation],
        system: str | None = None,
    ) -> AIConversationRecommendation:
        raise AIClientError("AI unavailable.")

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        raise AIClientError("AI unavailable.")


class ConversationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ConversationEngine(identify_stage_config)

    def test_identify_stage_config_uses_shared_engine_contract(self) -> None:
        self.assertEqual(identify_stage_config.stage, "identify")
        self.assertEqual(identify_stage_config.output_schema, "IdentifyOutput")
        self.assertIn("shared_rag_retrieval", identify_stage_config.available_tools)
        self.assertIn(
            "discovery_brief", identify_stage_config.required_structured_fields
        )
        self.assertEqual(len(identify_stage_config.question_evidence_areas), 20)
        self.assertGreater(len(identify_stage_config.cross_check_targets), 0)

    def test_answer_updates_context_and_asks_next_missing_field(self) -> None:
        context = self.engine.start_context()
        turn = ConversationTurn(
            role=ConversationRole.user,
            content=(
                "We build scheduling software for regional clinics and "
                "help managers reduce missed appointments."
            ),
        )

        result = self.engine.receive_turn(context, turn)

        self.assertEqual(result.action, ConversationAction.ask_question)
        self.assertEqual(len(result.context.turns), 2)
        self.assertIn("discovery_brief", result.context.collected_fields)
        self.assertIn("themes", result.missing_fields)
        self.assertTrue(result.output_valid)

    def test_vague_answer_revisits_relevant_topic(self) -> None:
        context = self.engine.start_context()
        turn = ConversationTurn(
            role=ConversationRole.user,
            content="Purpose matters.",
        )

        result = self.engine.receive_turn(context, turn)

        self.assertEqual(result.action, ConversationAction.revisit_topic)
        self.assertEqual(result.revisit_target, "social_contribution")
        self.assertTrue(result.next_question)
        self.assertEqual(
            result.context.cross_check_findings[-1].issue_type,
            CrossCheckIssueType.vagueness,
        )

    def test_contradiction_revisits_matching_cross_check_target(self) -> None:
        context = self.engine.start_context()
        first = ConversationTurn(
            role=ConversationRole.user,
            content=(
                "Our market position is premium support for clinics with complex "
                "operational needs."
            ),
        )
        context = self.engine.receive_turn(context, first).context
        second = ConversationTurn(
            role=ConversationRole.user,
            content=(
                "Our market position is not premium support; it is instead the "
                "lowest-cost option."
            ),
        )

        result = self.engine.receive_turn(context, second)

        self.assertEqual(result.action, ConversationAction.revisit_topic)
        self.assertEqual(result.revisit_target, "positioning")
        self.assertEqual(
            result.context.cross_check_findings[-1].issue_type,
            CrossCheckIssueType.contradiction,
        )

    def test_evidence_reference_without_source_uses_retrieval_placeholder(self) -> None:
        context = self.engine.start_context()
        turn = ConversationTurn(
            role=ConversationRole.user,
            content=(
                "The latest customer survey data shows clinics trust our service "
                "more than competitors."
            ),
        )

        result = self.engine.receive_turn(context, turn)

        self.assertEqual(result.action, ConversationAction.retrieve_evidence)
        self.assertEqual(
            result.context.retrieved_evidence, ["shared_rag_retrieval:pending"]
        )
        self.assertEqual(
            result.context.cross_check_findings[-1].issue_type,
            CrossCheckIssueType.gap,
        )

    def test_attached_evidence_is_kept_in_context_and_output_references(self) -> None:
        evidence = IdentifyEvidence(
            source=EvidenceSource(title="Customer Survey", source_type="survey"),
            claim="Customers report high trust.",
            confidence=0.8,
        )
        context = self.engine.start_context()
        turn = ConversationTurn(
            role=ConversationRole.user,
            content=(
                "The customer survey evidence shows clinics trust our service "
                "because support responds quickly."
            ),
            evidence=[evidence],
        )

        result = self.engine.receive_turn(context, turn)

        self.assertNotIn(
            "shared_rag_retrieval:pending", result.context.retrieved_evidence
        )
        self.assertEqual(result.context.evidence[0].id, evidence.id)
        self.assertEqual(result.structured_output["evidence_references"], [evidence.id])

    def test_ai_recommendation_can_supply_targeted_follow_up_question(self) -> None:
        recommendation = AIConversationRecommendation(
            recommended_action=ConversationAction.ask_question,
            next_question="What customer evidence supports that positioning?",
            structured_updates=[
                StructuredEvidenceUpdate(
                    field="positioning_evidence",
                    value="Clinics choose the product for responsive support.",
                    confidence=0.7,
                    evidence_required=True,
                )
            ],
        )
        ai_client = FakeAIClient(recommendation)
        engine = ConversationEngine(identify_stage_config, ai_client=ai_client)
        context = engine.start_context()

        result = engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="Our market position is support-led clinic software.",
            ),
        )

        self.assertEqual(result.action, ConversationAction.ask_question)
        self.assertEqual(
            result.next_question,
            "What customer evidence supports that positioning?",
        )
        self.assertEqual(
            result.structured_evidence_updates[0].field,
            "positioning_evidence",
        )
        self.assertIn("Latest answer:", ai_client.prompts[0])

    def test_ai_cannot_force_continue_when_required_fields_are_missing(self) -> None:
        recommendation = AIConversationRecommendation(
            recommended_action=ConversationAction.continue_stage,
            next_question="This should not control progression.",
        )
        engine = ConversationEngine(
            identify_stage_config,
            ai_client=FakeAIClient(recommendation),
        )

        result = engine.receive_turn(
            engine.start_context(),
            ConversationTurn(
                role=ConversationRole.user,
                content="We build scheduling software for regional clinics.",
            ),
        )

        self.assertEqual(result.action, ConversationAction.ask_question)

    def test_ai_revisit_target_must_match_configured_cross_check_target(self) -> None:
        recommendation = AIConversationRecommendation(
            recommended_action=ConversationAction.revisit_topic,
            revisit_target="unregistered_topic",
            next_question="Please revisit this unregistered area.",
        )
        engine = ConversationEngine(
            identify_stage_config,
            ai_client=FakeAIClient(recommendation),
        )

        result = engine.receive_turn(
            engine.start_context(),
            ConversationTurn(
                role=ConversationRole.user,
                content="We build scheduling software for regional clinics.",
            ),
        )

        self.assertNotEqual(result.action, ConversationAction.revisit_topic)
        self.assertIsNone(result.revisit_target)

    def test_next_question_avoids_repeating_previously_asked_question(self) -> None:
        context = self.engine.start_context()
        first_question = identify_stage_config.question_evidence_areas[0].question
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=first_question)
        )

        result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="We build scheduling software for regional clinics.",
            ),
        )

        self.assertNotEqual(result.next_question, first_question)

    def test_uncovered_area_is_preferred_before_partial_area(self) -> None:
        context = self.engine.start_context()
        partial_area = identify_stage_config.question_evidence_areas[0]
        uncovered_area = identify_stage_config.question_evidence_areas[1]
        context.question_area_statuses = {
            area.id: PlaybookCoverageStatus.sufficient
            for area in identify_stage_config.question_evidence_areas
        }
        context.question_area_statuses[partial_area.id] = PlaybookCoverageStatus.partial
        context.question_area_statuses[uncovered_area.id] = (
            PlaybookCoverageStatus.uncovered
        )

        result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.system,
                content="Select the next evidence area.",
            ),
        )

        self.assertEqual(result.next_question, uncovered_area.question)

    def test_partial_area_remains_eligible_when_no_area_is_uncovered(self) -> None:
        context = self.engine.start_context()
        partial_area = identify_stage_config.question_evidence_areas[0]
        context.question_area_statuses = {
            area.id: PlaybookCoverageStatus.sufficient
            for area in identify_stage_config.question_evidence_areas
        }
        context.question_area_statuses[partial_area.id] = PlaybookCoverageStatus.partial
        context.covered_question_area_ids = [
            area.id for area in identify_stage_config.question_evidence_areas
        ]

        result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.system,
                content="Select the next evidence area.",
            ),
        )

        self.assertEqual(result.next_question, partial_area.question)

    def test_sufficient_answer_can_progress_active_evidence_area(self) -> None:
        context = self.engine.start_context()
        area = identify_stage_config.question_evidence_areas[1]
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=area.question)
        )

        result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content=(
                    "At our best we remove the frustration of missed clinic "
                    "appointments by automating reminders and giving managers "
                    "clear scheduling visibility."
                ),
            ),
        )

        self.assertIn(area.id, result.context.covered_question_area_ids)
        self.assertIn(area.structured_field, result.context.collected_fields)

    def test_vague_answer_does_not_progress_active_evidence_area(self) -> None:
        context = self.engine.start_context()
        area = identify_stage_config.question_evidence_areas[1]
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=area.question)
        )

        result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="We make things better for them.",
            ),
        )

        self.assertEqual(result.action, ConversationAction.revisit_topic)
        self.assertNotIn(area.id, result.context.covered_question_area_ids)

    def test_vague_answer_gets_targeted_follow_up_for_same_evidence_area(
        self,
    ) -> None:
        context = self.engine.start_context()
        area = identify_stage_config.question_evidence_areas[1]
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=area.question)
        )

        result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="We make things better for them.",
            ),
        )

        self.assertEqual(result.revisit_target, area.id)
        self.assertNotEqual(result.next_question, area.question)
        self.assertIn(area.label.lower(), result.next_question.lower())
        self.assertIn(area.evidence_prompt, result.next_question)

    def test_useful_clarification_can_progress_after_vague_answer(self) -> None:
        context = self.engine.start_context()
        area = identify_stage_config.question_evidence_areas[1]
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=area.question)
        )
        vague_result = self.engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="We make things better for them.",
            ),
        )

        result = self.engine.receive_turn(
            vague_result.context,
            ConversationTurn(
                role=ConversationRole.user,
                content=(
                    "Specifically, we remove the cost and stress of missed "
                    "appointments for clinic managers by sending automated "
                    "reminders and showing which patients need follow-up."
                ),
            ),
        )

        self.assertIn(area.id, result.context.covered_question_area_ids)
        self.assertIn(area.structured_field, result.context.collected_fields)
        self.assertNotEqual(result.next_question, vague_result.next_question)

    def test_ai_failure_fallback_does_not_mark_vague_answer_complete(self) -> None:
        engine = ConversationEngine(
            identify_stage_config,
            ai_client=FailingAIClient(),
        )
        context = engine.start_context()
        area = identify_stage_config.question_evidence_areas[1]
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=area.question)
        )

        result = engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="We make things better for them.",
            ),
        )

        self.assertEqual(result.action, ConversationAction.revisit_topic)
        self.assertNotIn(area.id, result.context.covered_question_area_ids)
        self.assertEqual(result.structured_evidence_updates, [])

    def test_ai_update_does_not_mark_vague_answer_complete(self) -> None:
        area = identify_stage_config.question_evidence_areas[1]
        recommendation = AIConversationRecommendation(
            recommended_action=ConversationAction.ask_question,
            next_question="What outcome changes for the customer?",
            structured_updates=[
                StructuredEvidenceUpdate(
                    field=area.structured_field,
                    value="The organisation improves outcomes for customers.",
                    confidence=0.7,
                )
            ],
        )
        engine = ConversationEngine(
            identify_stage_config,
            ai_client=FakeAIClient(recommendation),
        )
        context = engine.start_context()
        context.turns.append(
            ConversationTurn(role=ConversationRole.assistant, content=area.question)
        )

        result = engine.receive_turn(
            context,
            ConversationTurn(
                role=ConversationRole.user,
                content="We make things better for them.",
            ),
        )

        self.assertEqual(result.action, ConversationAction.revisit_topic)
        self.assertNotIn(area.id, result.context.covered_question_area_ids)
        self.assertEqual(result.structured_evidence_updates, [])


if __name__ == "__main__":
    unittest.main()
