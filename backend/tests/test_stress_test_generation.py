import unittest
from uuid import UUID, uuid4

from app.schemas.assessment import (
    DefineApprovalStatus,
    DefineOutput,
    DefineProvenance,
    EvidenceStatus,
    PositioningStatement,
    SingleOrganizingIdeaCandidate,
    StressTestCriterionResult,
    StressTestCriterionStatus,
    StressTestState,
    ValueChainMoment,
    ValueCommitment,
)
from app.services.ai_client import AIClientError
from app.services.define_evidence import DefineEvidenceRecord
from app.services.stress_test import (
    CRITERION_GUIDES,
    LEGACY_REASONING,
    OVERARCHING_QUESTION,
    STRESS_TEST_CRITERIA,
    StressTestProposal,
    _previous_fallback_reasoning,
    evaluate_stress_test,
    recover_legacy_stress_test,
)


class FailingStressAI:
    def generate_structured(self, prompt, output_schema, system=None):
        raise AIClientError("Unavailable")


class ProposalStressAI:
    def __init__(self, factory) -> None:
        self.factory = factory
        self.prompt = None

    def generate_structured(self, prompt, output_schema, system=None):
        self.prompt = prompt
        return self.factory(output_schema)


class StressTestGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ids = {
            name: uuid4()
            for name in (
                "credible",
                "resilient",
                "relevant",
                "commercial",
                "beneficial",
                "single",
                "organizing",
                "idea",
            )
        }
        self.records = {
            self.ids["credible"]: self._record(
                "credible",
                "Independent governance and externally verified operating facts.",
                "organisation_basics",
            ),
            self.ids["resilient"]: self._record(
                "resilient",
                "Regulatory and technology change create long-term pressure.",
                "vulnerabilities",
            ),
            self.ids["relevant"]: self._record(
                "relevant",
                "Customers need reliable access and service.",
                "customer_needs",
            ),
            self.ids["commercial"]: self._record(
                "commercial",
                "Operating costs and reserves affect financial sustainability.",
                "economic_context",
            ),
            self.ids["beneficial"]: self._record(
                "beneficial",
                "Community health programmes support social wellbeing.",
                "social_contribution",
            ),
            self.ids["single"]: self._record(
                "single",
                "A recurring purpose theme supplies decision focus.",
                "purpose_driven_proof",
            ),
            self.ids["organizing"]: self._record(
                "organizing",
                "Employees and partners translate decisions into service.",
                "employee_experience",
            ),
            self.ids["idea"]: self._record(
                "idea",
                "The founding identity has trusted brand resonance.",
                "best_work",
            ),
        }
        self.define_output = DefineOutput(
            agreedSoi=SingleOrganizingIdeaCandidate(
                statement="A clear shared purpose",
                evidenceIds=[self.ids["credible"], self.ids["single"]],
                approvalStatus=DefineApprovalStatus.agreed,
            ),
            agreedPositioning=PositioningStatement(
                audience="Customers",
                categoryContext="service organisation",
                capabilityValue="delivers reliable value",
                reasonBelievability="documented operating evidence",
                composedStatement="A documented service position.",
                evidenceIds=[self.ids["commercial"], self.ids["relevant"]],
                approvalStatus=DefineApprovalStatus.agreed,
            ),
            agreedValues=[
                ValueCommitment(
                    name="Positive impact",
                    meaning="Benefit people and communities.",
                    evidenceIds=[self.ids["beneficial"], self.ids["idea"]],
                    approvalStatus=DefineApprovalStatus.agreed,
                )
            ],
            agreedMoments=[
                ValueChainMoment(
                    name="Service delivery",
                    evidenceIds=[self.ids["organizing"], self.ids["relevant"]],
                    approvalStatus=DefineApprovalStatus.agreed,
                )
            ],
            evidenceReferences=list(self.records),
        )

    def test_fixed_methodology_and_specific_fallbacks_are_preserved(self) -> None:
        state = self._evaluate()

        self.assertEqual(
            [(item.criterion_id, item.name, item.question) for item in state.criteria],
            list(STRESS_TEST_CRITERIA),
        )
        self.assertEqual(state.overarching_question, OVERARCHING_QUESTION)
        self.assertFalse(hasattr(state, "score"))
        self.assertFalse(hasattr(state, "weight"))
        self.assertFalse(hasattr(state, "threshold"))
        self.assertEqual(len({item.reasoning for item in state.criteria}), 8)
        self.assertTrue(
            all(item.reasoning != LEGACY_REASONING for item in state.criteria)
        )
        for item in state.criteria:
            self.assertIn(
                CRITERION_GUIDES[item.criterion_id].evidence_focus,
                item.reasoning,
            )
        self.assertTrue(all(item.concerns for item in state.criteria))
        self.assertGreater(len({tuple(item.concerns) for item in state.criteria}), 1)
        self.assertTrue(
            all(item.suggested_refinement is None for item in state.criteria)
        )
        self.assertTrue(
            all(
                item.provenance.status == EvidenceStatus.source_derived
                for item in state.criteria
            )
        )

    def test_criteria_receive_valid_different_bounded_evidence(self) -> None:
        state = self._evaluate()
        evidence_sets = [tuple(item.supporting_evidence_ids) for item in state.criteria]

        self.assertGreater(len(set(evidence_sets)), 1)
        for item in state.criteria:
            self.assertLessEqual(len(item.supporting_evidence_ids), 8)
            self.assertTrue(set(item.supporting_evidence_ids).issubset(self.records))
            self.assertIn(self.ids[item.criterion_id], item.supporting_evidence_ids)

        beneficial = next(
            item for item in state.criteria if item.criterion_id == "beneficial"
        )
        self.assertIn("planet", beneficial.concerns[0])
        organizing = next(
            item for item in state.criteria if item.criterion_id == "organizing"
        )
        self.assertIn("functions", organizing.concerns[0])

    def test_fallback_synthesizes_themes_without_raw_evidence_labels(self) -> None:
        noisy_records = dict(self.records)
        noisy_records[self.ids["credible"]] = DefineEvidenceRecord(
            id=self.ids["credible"],
            kind="identify-evidence",
            title="About Example group | Example Organisation",
            text="Independent governance and externally verified operating facts.",
            summary="The rollout of a service platform, operating changes...",
            source_activity="test",
            coverage_area_ids=("organisation_basics", "performance_governance"),
        )

        state = evaluate_stress_test(
            uuid4(),
            self.define_output,
            evidence_records=noisy_records,
        )

        expected_themes = {
            "credible": "organisational identity and operating reality",
            "resilient": "technology change and digital service development",
            "relevant": "member and customer needs",
            "commercial": "financial and claims performance",
            "beneficial": "community and social contribution",
            "single": "recurring purpose and identity themes",
            "organizing": "employee and functional context",
            "idea": "founding purpose and organisational identity",
        }
        for item in state.criteria:
            self.assertIn(expected_themes[item.criterion_id], item.reasoning)
            self.assertNotIn("About Example group", item.reasoning)
            self.assertNotIn("|", item.reasoning)
            self.assertNotIn("...", item.reasoning)
            self.assertNotIn("Evidence about", item.reasoning)
        self.assertEqual(len({item.reasoning for item in state.criteria}), 8)

    def test_previous_fallback_recovery_changes_reasoning_only(self) -> None:
        state = self._evaluate()
        for item in state.criteria:
            records = [self.records[evidence_id] for evidence_id in item.supporting_evidence_ids]
            item.reasoning = _previous_fallback_reasoning(
                self.define_output,
                records,
                CRITERION_GUIDES[item.criterion_id],
            )
        before = {
            item.criterion_id: item.model_dump(exclude={"reasoning"})
            for item in state.criteria
        }

        recovered = recover_legacy_stress_test(
            state,
            self.define_output,
            evidence_records=self.records,
        )

        for item in recovered.criteria:
            self.assertEqual(item.model_dump(exclude={"reasoning"}), before[item.criterion_id])
            self.assertNotIn("Evidence about", item.reasoning)
        second = recover_legacy_stress_test(
            recovered,
            self.define_output,
            evidence_records=self.records,
        )
        self.assertEqual(second, recovered)

    def test_absent_resolved_evidence_is_insufficient(self) -> None:
        state = evaluate_stress_test(
            uuid4(),
            self.define_output,
            evidence_records={},
        )

        self.assertTrue(
            all(
                item.status == StressTestCriterionStatus.insufficient_evidence
                for item in state.criteria
            )
        )
        self.assertTrue(
            all(not item.supporting_evidence_ids for item in state.criteria)
        )

    def test_ai_failure_uses_source_derived_specific_fallback(self) -> None:
        state = self._evaluate(ai_client=FailingStressAI())

        self.assertTrue(
            all(item.reasoning != LEGACY_REASONING for item in state.criteria)
        )
        self.assertTrue(
            all(
                item.provenance.status == EvidenceStatus.source_derived
                for item in state.criteria
            )
        )

    def test_valid_ai_proposal_is_preserved(self) -> None:
        client = ProposalStressAI(self._valid_ai_proposal)

        state = self._evaluate(ai_client=client)

        self.assertTrue(
            all(
                item.reasoning.startswith("AI analysis for")
                for item in state.criteria
            )
        )
        self.assertTrue(
            all(
                item.provenance.status == EvidenceStatus.ai_inferred
                for item in state.criteria
            )
        )
        self.assertTrue(
            all(item.approval_status == "ai-proposed" for item in state.criteria)
        )
        self.assertIn("Criterion contexts", client.prompt)
        self.assertIn('"agreedMomentsOfTruth"', client.prompt)
        self.assertNotIn('"completionStatus"', client.prompt)

    def test_malformed_ai_output_falls_back(self) -> None:
        client = ProposalStressAI(lambda schema: schema(criteria=[]))

        state = self._evaluate(ai_client=client)

        self.assertTrue(
            all(item.reasoning != LEGACY_REASONING for item in state.criteria)
        )
        self.assertTrue(
            all(item.provenance.status == "source-derived" for item in state.criteria)
        )

    def test_unknown_ai_evidence_id_cannot_persist(self) -> None:
        unknown = uuid4()

        def proposal(schema):
            valid = self._valid_ai_proposal(schema)
            first = valid.criteria[0].model_copy(update={"evidence_ids": [unknown]})
            return valid.model_copy(update={"criteria": [first, *valid.criteria[1:]]})

        state = self._evaluate(ai_client=ProposalStressAI(proposal))

        self.assertTrue(
            all(
                unknown not in item.supporting_evidence_ids
                for item in state.criteria
            )
        )
        self.assertTrue(
            all(item.provenance.status == "source-derived" for item in state.criteria)
        )

    def test_legacy_recovery_protects_human_reviews_and_is_idempotent(self) -> None:
        state = self._legacy_state()
        state.criteria[2].question = (
            "Will the SOI® deliver value to our business and our stakeholders?"
        )
        state.overarching_response = "Preserve this human response."
        state.version = 4
        define_before = self.define_output.model_copy(deep=True)
        custom_user = state.criteria[0].model_copy(
            update={
                "reasoning": "User-specific credible review.",
                "approval_status": DefineApprovalStatus.user_edited,
            },
            deep=True,
        )
        custom_agreed = state.criteria[1].model_copy(
            update={
                "reasoning": "Agreed resilient review.",
                "approval_status": DefineApprovalStatus.agreed,
            },
            deep=True,
        )
        state.criteria[0] = custom_user
        state.criteria[1] = custom_agreed

        recovered = recover_legacy_stress_test(
            state,
            self.define_output,
            evidence_records=self.records,
        )

        self.assertEqual(recovered.criteria[0], custom_user)
        self.assertEqual(recovered.criteria[1], custom_agreed)
        self.assertEqual(recovered.overarching_response, state.overarching_response)
        self.assertEqual(recovered.version, state.version)
        self.assertEqual(self.define_output, define_before)
        self.assertTrue(
            all(
                item.reasoning != LEGACY_REASONING
                for item in recovered.criteria[2:]
            )
        )
        second = recover_legacy_stress_test(
            recovered,
            self.define_output,
            evidence_records=self.records,
        )
        self.assertEqual(second, recovered)

    def _evaluate(self, ai_client=None):
        return evaluate_stress_test(
            uuid4(),
            self.define_output,
            evidence_records=self.records,
            ai_client=ai_client,
        )

    def _valid_ai_proposal(self, schema) -> StressTestProposal:
        return schema(
            criteria=[
                {
                    "criterionId": criterion_id,
                    "question": question,
                    "status": "needs-review",
                    "reasoning": f"AI analysis for {criterion_id}.",
                    "concerns": [f"Human review remains for {criterion_id}."],
                    "suggestedRefinement": None,
                    "evidenceIds": [self.ids[criterion_id]],
                }
                for criterion_id, _, question in STRESS_TEST_CRITERIA
            ]
        )

    def _legacy_state(self) -> StressTestState:
        provenance = DefineProvenance(
            status=EvidenceStatus.ai_inferred,
            rationale=(
                "Deterministic framework initialized from the agreed Define handoff."
            ),
            sourceHandoff="structured_outputs.define.handoff",
        )
        evidence = list(self.records)
        return StressTestState(
            assessmentId=uuid4(),
            status="ready_for_review",
            criteria=[
                StressTestCriterionResult(
                    criterionId=criterion_id,
                    name=name,
                    question=question,
                    status="needs-review",
                    reasoning=LEGACY_REASONING,
                    supportingEvidenceIds=evidence,
                    concerns=[],
                    suggestedRefinement=None,
                    provenance=provenance,
                )
                for criterion_id, name, question in STRESS_TEST_CRITERIA
            ],
            overarchingQuestion=OVERARCHING_QUESTION,
            evidenceReferences=evidence,
            provenance=provenance,
        )

    def _record(
        self,
        title: str,
        text: str,
        coverage: str,
    ) -> DefineEvidenceRecord:
        evidence_id = self.ids[title]
        return DefineEvidenceRecord(
            id=evidence_id,
            kind="identify-evidence",
            title=f"{title.title()} evidence",
            text=text,
            summary=f"{title.title()} evidence",
            source_activity="test",
            coverage_area_ids=(coverage,),
        )


if __name__ == "__main__":
    unittest.main()
