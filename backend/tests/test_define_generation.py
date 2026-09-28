import unittest
from uuid import UUID, uuid4

from app.schemas.assessment import (
    EvidenceSource,
    EvidenceStatus,
    DefineApprovalStatus,
    IdentifyEvidence,
    PESTLEFinding,
    PositioningStatement,
    ResearchFinding,
    ResearchSourceType,
    SingleOrganizingIdeaCandidate,
    ValueChainMoment,
    ValueChainMomentStatus,
    ValueCommitment,
)
from app.services.ai_client import AIClientError
from app.services.define_generation import (
    DefineProposal,
    generate_define_state,
    repair_moments,
    repair_value_meanings,
)
from app.services.identify_completion import get_persisted_identify_handoff
from app.store.sessions import session_store
from backend.tests.test_identify_brief_api import complete_identify_inputs, request


class ProposalAIClient:
    def __init__(self, proposal: DefineProposal) -> None:
        self.proposal = proposal
        self.calls = 0

    def generate_structured(self, prompt, output_schema, system=None):
        self.calls += 1
        return self.proposal


class FailingAIClient:
    def generate_structured(self, prompt, output_schema, system=None):
        raise AIClientError("Define generation unavailable.")


class DefineGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()
        session_id = complete_identify_inputs()
        session_store.update_identify_pestle_findings(
            UUID(session_id),
            [
                PESTLEFinding(
                    category="technological",
                    signal="Service expectations are changing",
                    description="Customers expect more responsive service.",
                    whyItMatters="The operating experience must keep pace.",
                    opportunityOrRisk="An opportunity to improve responsiveness.",
                )
            ],
        )
        request("POST", f"/api/sessions/{session_id}/identify/complete")
        session = session_store.get(UUID(session_id))
        assert session is not None
        self.handoff = get_persisted_identify_handoff(session)
        assert self.handoff is not None

    def test_open_questions_are_deduplicated_in_first_seen_order(self) -> None:
        handoff = self.handoff.model_copy(
            update={"open_questions": ["shared", "handoff-only", "shared"]},
            deep=True,
        )
        proposal = self._proposal(
            SingleOrganizingIdeaCandidate(statement="Care in motion")
        ).model_copy(
            update={"unresolved_questions": ["proposal-only", "shared"]},
            deep=True,
        )

        state = generate_define_state(
            handoff,
            ai_client=ProposalAIClient(proposal),
        )

        self.assertEqual(
            state.unresolved_questions,
            ["proposal-only", "shared", "handoff-only"],
        )

    def test_fallback_open_question_generation_is_idempotent(self) -> None:
        handoff = self.handoff.model_copy(
            update={"open_questions": ["first", "second", "first"]},
            deep=True,
        )

        first = generate_define_state(handoff)
        second = generate_define_state(handoff)

        self.assertEqual(first.unresolved_questions, ["first", "second"])
        self.assertEqual(second.unresolved_questions, first.unresolved_questions)

    def test_valid_ai_soi_and_other_ai_fields_are_retained(self) -> None:
        proposal = self._proposal(
            SingleOrganizingIdeaCandidate(statement="Care in motion")
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(proposal),
        )

        assert state.soi_candidate is not None
        self.assertEqual(state.soi_candidate.statement, "Care in motion")
        self.assertEqual(state.positioning.audience, "AI audience")
        self.assertEqual(state.values[0].name, "AI commitment")
        self.assertEqual(state.moments[0].name, "AI moment")

    def test_complete_ai_positioning_is_retained(self) -> None:
        positioning = PositioningStatement(
            audience="AI audience",
            categoryContext="AI category",
            capabilityValue="AI capability",
            reasonBelievability="AI reason",
            composedStatement="AI composed statement",
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(
                self._proposal(
                    SingleOrganizingIdeaCandidate(statement="Care in motion"),
                    positioning=positioning,
                )
            ),
        )

        self.assertEqual(state.positioning.audience, "AI audience")
        self.assertEqual(state.positioning.category_context, "AI category")
        self.assertEqual(state.positioning.capability_value, "AI capability")
        self.assertEqual(state.positioning.reason_believability, "AI reason")
        self.assertEqual(
            state.positioning.composed_statement,
            "AI composed statement",
        )

    def test_incomplete_ai_positioning_uses_fallback_per_field(self) -> None:
        positioning = PositioningStatement(
            audience="AI audience",
            categoryContext=None,
            capabilityValue="   ",
            reasonBelievability=None,
            composedStatement=None,
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(
                self._proposal(
                    SingleOrganizingIdeaCandidate(statement="Care in motion"),
                    positioning=positioning,
                )
            ),
        )

        self.assertEqual(state.positioning.audience, "AI audience")
        self.assertTrue(state.positioning.category_context.strip())
        self.assertTrue(state.positioning.capability_value.strip())
        self.assertTrue(state.positioning.reason_believability.strip())
        self.assertTrue(state.positioning.composed_statement.strip())
        self.assertIn("AI audience", state.positioning.composed_statement)

    def test_failed_or_missing_ai_produces_complete_fallback_positioning(self) -> None:
        for client in (FailingAIClient(), None):
            with self.subTest(client=type(client).__name__):
                state = generate_define_state(self.handoff, ai_client=client)
                self.assertTrue(state.positioning.audience.strip())
                self.assertTrue(state.positioning.category_context.strip())
                self.assertTrue(state.positioning.capability_value.strip())
                self.assertTrue(state.positioning.reason_believability.strip())
                self.assertTrue(state.positioning.composed_statement.strip())

    def test_null_ai_soi_preserves_fallback_and_other_ai_fields(self) -> None:
        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(self._proposal(None)),
        )

        assert state.soi_candidate is not None
        self.assertTrue(state.soi_candidate.statement.strip())
        self.assertEqual(state.positioning.audience, "AI audience")
        self.assertEqual(state.values[0].name, "AI commitment")
        self.assertEqual(state.moments[0].name, "AI moment")

    def test_blank_ai_soi_preserves_fallback(self) -> None:
        blank = SingleOrganizingIdeaCandidate.model_construct(statement="")
        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(self._proposal(blank)),
        )

        assert state.soi_candidate is not None
        self.assertTrue(state.soi_candidate.statement.strip())

    def test_whitespace_ai_soi_preserves_fallback(self) -> None:
        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(
                self._proposal(SingleOrganizingIdeaCandidate(statement="   "))
            ),
        )

        assert state.soi_candidate is not None
        self.assertTrue(state.soi_candidate.statement.strip())

    def test_ai_failure_uses_fallback_soi(self) -> None:
        state = generate_define_state(
            self.handoff,
            ai_client=FailingAIClient(),
        )

        assert state.soi_candidate is not None
        self.assertTrue(state.soi_candidate.statement.strip())

    def test_no_ai_client_uses_fallback_soi(self) -> None:
        state = generate_define_state(self.handoff)

        assert state.soi_candidate is not None
        self.assertTrue(state.soi_candidate.statement.strip())

    def test_missing_ai_value_meaning_uses_evidence_matched_fallback(self) -> None:
        first_id = uuid4()
        second_id = uuid4()
        fallbacks = [
            ValueCommitment(
                name="Dependable service",
                meaning="Keep essential services dependable for local households.",
                evidenceIds=[first_id],
            ),
            ValueCommitment(
                name="Shared prosperity",
                meaning="Help local producers build secure livelihoods.",
                evidenceIds=[second_id],
            ),
        ]

        for missing in (None, "", "   "):
            with self.subTest(meaning=missing):
                value = ValueCommitment(
                    name="AI producer commitment",
                    meaning=None,
                    evidenceIds=[second_id],
                ).model_copy(update={"meaning": missing})
                repaired = repair_value_meanings(
                    [value],
                    list(reversed(fallbacks)),
                    handoff=self.handoff,
                )[0]

                self.assertEqual(repaired.id, value.id)
                self.assertEqual(repaired.name, value.name)
                self.assertEqual(repaired.evidence_ids, value.evidence_ids)
                self.assertEqual(repaired.provenance, value.provenance)
                self.assertEqual(repaired.meaning, fallbacks[1].meaning)

    def test_value_recovery_preserves_valid_and_user_authoritative_values(self) -> None:
        evidence_id = uuid4()
        fallback = ValueCommitment(
            name="Evidence-backed service",
            meaning="Fallback meaning",
            evidenceIds=[evidence_id],
        )
        values = [
            ValueCommitment(
                name="Valid AI value",
                meaning="Preserve this AI meaning.",
                evidenceIds=[evidence_id],
            ),
            ValueCommitment(
                name="Edited value",
                meaning=None,
                evidenceIds=[evidence_id],
                approvalStatus=DefineApprovalStatus.user_edited,
            ),
            ValueCommitment(
                name="Agreed value",
                meaning=None,
                evidenceIds=[evidence_id],
                approvalStatus=DefineApprovalStatus.agreed,
            ),
        ]

        repaired = repair_value_meanings(values, [fallback], handoff=self.handoff)

        self.assertEqual(repaired, values)

    def test_multiple_values_match_evidence_not_array_position(self) -> None:
        first_id = uuid4()
        second_id = uuid4()
        ai_values = [
            ValueCommitment(name="AI first", evidenceIds=[second_id]),
            ValueCommitment(name="AI second", evidenceIds=[first_id]),
        ]
        fallbacks = [
            ValueCommitment(
                name="Fallback first",
                meaning="Meaning supported by the first evidence item.",
                evidenceIds=[first_id],
            ),
            ValueCommitment(
                name="Fallback second",
                meaning="Meaning supported by the second evidence item.",
                evidenceIds=[second_id],
            ),
        ]

        repaired = repair_value_meanings(
            ai_values,
            fallbacks,
            handoff=self.handoff,
        )

        self.assertEqual(repaired[0].meaning, fallbacks[1].meaning)
        self.assertEqual(repaired[1].meaning, fallbacks[0].meaning)

    def test_value_meaning_uses_its_referenced_cross_company_evidence(self) -> None:
        source = self._research(
            "Local producer support",
            "Harbour Mutual helps local producers access shared distribution services.",
        )
        handoff = self.handoff.model_copy(
            update={
                "output": self.handoff.output.model_copy(
                    update={"research_findings": [source]},
                    deep=True,
                )
            },
            deep=True,
        )
        value = ValueCommitment(
            name="Producer access",
            evidenceIds=[source.id],
        )

        repaired = repair_value_meanings([value], [], handoff=handoff)[0]

        self.assertEqual(repaired.meaning, source.summary)
        self.assertNotIn("Southern Cross", repaired.meaning)

    def test_internal_fallback_summary_is_not_exposed_as_value_meaning(self) -> None:
        source = self._research(
            "Local service",
            "Harbour Mutual provides dependable local services for its members.",
        )
        handoff = self.handoff.model_copy(
            update={
                "output": self.handoff.output.model_copy(
                    update={"research_findings": [source]},
                    deep=True,
                )
            },
            deep=True,
        )
        value = ValueCommitment(name="Dependable service", evidenceIds=[source.id])
        fallback = ValueCommitment(
            name="Service evidence",
            meaning="7 evidence items clustered on the Evidence Wall.",
            evidenceIds=[source.id],
        )

        repaired = repair_value_meanings([value], [fallback], handoff=handoff)[0]

        self.assertEqual(repaired.meaning, source.summary)
        self.assertNotIn("Evidence Wall", repaired.meaning)

    def test_value_recovery_is_idempotent_and_sparse_evidence_is_unchanged(self) -> None:
        sparse = ValueCommitment(name="Unsupported commitment", evidenceIds=[uuid4()])

        first = repair_value_meanings([sparse], [], handoff=self.handoff)
        second = repair_value_meanings(first, [], handoff=self.handoff)

        self.assertEqual(first, [sparse])
        self.assertEqual(second, first)

    def test_ai_value_repair_does_not_change_other_define_fields(self) -> None:
        theme = self.handoff.brief.themes[0]
        proposal = self._proposal(
            SingleOrganizingIdeaCandidate(statement="Care in motion"),
            values=[
                ValueCommitment(
                    name="AI commitment",
                    evidenceIds=theme.evidence_ids,
                )
            ],
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(proposal),
        )

        self.assertTrue(state.values[0].meaning.strip())
        self.assertNotIn("Evidence Wall", state.values[0].meaning)
        self.assertEqual(state.soi_candidate.statement, "Care in motion")
        self.assertEqual(state.positioning.audience, "AI audience")
        self.assertEqual(state.moments[0].name, "AI moment")

    def test_complete_ai_moment_is_preserved_unchanged(self) -> None:
        moment = ValueChainMoment(
            name="Member support",
            question="What should members experience when they need support?",
            today="Members receive responsive support.",
            desiredState="Members consistently receive clear help.",
            theMove="Keep monitoring response quality.",
            status=ValueChainMomentStatus.on_course,
            supportingEvidence=["Member interviews describe responsive support."],
            evidenceIds=[uuid4()],
        )
        fallback = moment.model_copy(
            update={
                "question": "Fallback question",
                "status": ValueChainMomentStatus.gap_to_close,
            }
        )

        repaired = repair_moments([moment], [fallback], handoff=self.handoff)

        self.assertEqual(repaired, [moment])

    def test_moment_fields_and_status_recover_by_evidence_not_position(self) -> None:
        first_id = uuid4()
        target_id = uuid4()
        fallback_other = ValueChainMoment(
            name="Other moment",
            question="Other question",
            evidenceIds=[first_id],
        )
        fallback_target = ValueChainMoment(
            name="Producer onboarding",
            question="What should local producers experience during onboarding?",
            today="Onboarding currently requires several manual steps.",
            desiredState="Producers receive a clear and dependable start.",
            theMove="Create one shared onboarding checklist.",
            status=ValueChainMomentStatus.gap_to_close,
            supportingEvidence=[
                "Producer interviews identify repeated manual onboarding steps.",
                "Great",
            ],
            evidenceIds=[target_id],
        )
        moment = ValueChainMoment(
            name="AI onboarding",
            question="Preserve this valid AI question.",
            evidenceIds=[target_id],
        )

        repaired = repair_moments(
            [moment],
            [fallback_other, fallback_target],
            handoff=self.handoff,
        )[0]

        self.assertEqual(repaired.id, moment.id)
        self.assertEqual(repaired.name, moment.name)
        self.assertEqual(repaired.question, moment.question)
        self.assertEqual(repaired.today, fallback_target.today)
        self.assertEqual(repaired.desired_state, fallback_target.desired_state)
        self.assertEqual(repaired.the_move, fallback_target.the_move)
        self.assertEqual(repaired.status, ValueChainMomentStatus.gap_to_close)
        self.assertEqual(
            repaired.supporting_evidence,
            ["Producer interviews identify repeated manual onboarding steps."],
        )
        self.assertEqual(repaired.evidence_ids, moment.evidence_ids)
        self.assertEqual(repaired.provenance, moment.provenance)
        self.assertEqual(repaired.approval_status, moment.approval_status)

    def test_moment_name_match_recovers_fields_without_array_position(self) -> None:
        unrelated = ValueChainMoment(
            name="Unrelated",
            question="Do not use this question?",
        )
        quote = ValueChainMoment(
            name="Getting a quote",
            question="What should customers experience when getting a quote?",
            today="Quotes are currently easy to request.",
            desiredState="Quote requests should feel reliable.",
            theMove=None,
            status=ValueChainMomentStatus.on_course,
        )
        moment = ValueChainMoment(name="Quote Generation")

        repaired = repair_moments(
            [moment],
            [unrelated, quote],
            handoff=self.handoff,
        )[0]

        self.assertEqual(repaired.question, quote.question)
        self.assertEqual(repaired.today, quote.today)
        self.assertEqual(repaired.desired_state, quote.desired_state)
        self.assertIsNone(repaired.the_move)
        self.assertEqual(repaired.status, ValueChainMomentStatus.on_course)

    def test_moment_matches_referenced_touchpoint_source_when_names_differ(self) -> None:
        touchpoint = self.handoff.output.stakeholder_journeys[0].touchpoints[0]
        fallback = ValueChainMoment(
            name=touchpoint.moment,
            question="What should customers experience through this channel?",
            today="The channel is currently easy to use.",
            desiredState="The channel should remain dependable.",
            theMove="Keep monitoring the channel experience.",
            status=ValueChainMomentStatus.in_progress,
        )
        moment = ValueChainMoment(
            name="Member portal",
            evidenceIds=[touchpoint.id],
        )

        repaired = repair_moments([moment], [fallback], handoff=self.handoff)[0]

        self.assertEqual(repaired.question, fallback.question)
        self.assertEqual(repaired.today, fallback.today)
        self.assertEqual(repaired.status, fallback.status)

    def test_unmatched_moment_uses_only_its_referenced_evidence(self) -> None:
        source = self._research(
            "Producer service",
            "Harbour Mutual currently provides shared services to local producers.",
        )
        handoff = self.handoff.model_copy(
            update={
                "output": self.handoff.output.model_copy(
                    update={"research_findings": [source]},
                    deep=True,
                )
            },
            deep=True,
        )
        moment = ValueChainMoment(
            name="Producer settlement",
            evidenceIds=[source.id],
        )
        positional_fallback = ValueChainMoment(
            name="Warehouse dispatch",
            question="This must not be copied by position.",
            today="Unrelated fallback state.",
            desiredState="Unrelated future state.",
            theMove="Unrelated move.",
            status=ValueChainMomentStatus.gap_to_close,
        )

        repaired = repair_moments(
            [moment],
            [positional_fallback],
            handoff=handoff,
        )[0]

        self.assertIsNone(repaired.question)
        self.assertEqual(repaired.today, source.summary)
        self.assertIsNone(repaired.desired_state)
        self.assertIsNone(repaired.the_move)
        self.assertEqual(repaired.status, ValueChainMomentStatus.in_progress)
        self.assertEqual(repaired.supporting_evidence, [source.summary])
        self.assertNotIn("Southern Cross", repaired.today)

    def test_moment_without_supported_move_keeps_move_null(self) -> None:
        evidence_id = uuid4()
        fallback = ValueChainMoment(
            name="Renewal",
            question="What should customers experience at renewal?",
            today="Renewal is currently straightforward.",
            desiredState="Renewal should continue to feel reliable.",
            theMove=None,
            status=ValueChainMomentStatus.on_course,
            evidenceIds=[evidence_id],
        )
        repaired = repair_moments(
            [ValueChainMoment(name="Renewal", evidenceIds=[evidence_id])],
            [fallback],
            handoff=self.handoff,
        )[0]

        self.assertIsNone(repaired.the_move)
        self.assertEqual(repaired.status, ValueChainMomentStatus.on_course)

    def test_blank_and_whitespace_moment_fields_are_recovered(self) -> None:
        evidence_id = uuid4()
        fallback = ValueChainMoment(
            name="Service handoff",
            question="What should customers experience at the service handoff?",
            today="The handoff currently includes a manual confirmation.",
            desiredState="Customers receive a clear confirmation.",
            theMove="Standardise the confirmation step.",
            supportingEvidence=["Journey evidence records a manual confirmation."],
            evidenceIds=[evidence_id],
        )
        blank = ValueChainMoment(
            name="Service handoff",
            evidenceIds=[evidence_id],
        ).model_copy(
            update={
                "question": "",
                "today": "   ",
                "desired_state": "\t",
                "the_move": " ",
                "supporting_evidence": ["   "],
            }
        )

        repaired = repair_moments([blank], [fallback], handoff=self.handoff)[0]

        self.assertEqual(repaired.question, fallback.question)
        self.assertEqual(repaired.today, fallback.today)
        self.assertEqual(repaired.desired_state, fallback.desired_state)
        self.assertEqual(repaired.the_move, fallback.the_move)
        self.assertEqual(repaired.supporting_evidence, fallback.supporting_evidence)

    def test_user_edited_and_agreed_moments_are_authoritative(self) -> None:
        evidence_id = uuid4()
        fallback = ValueChainMoment(
            name="Fallback",
            question="Fallback question",
            today="Fallback today",
            evidenceIds=[evidence_id],
            status=ValueChainMomentStatus.on_course,
        )
        moments = [
            ValueChainMoment(
                name="Edited",
                evidenceIds=[evidence_id],
                status=ValueChainMomentStatus.gap_to_close,
                approvalStatus=DefineApprovalStatus.user_edited,
            ),
            ValueChainMoment(
                name="Agreed",
                evidenceIds=[evidence_id],
                status=ValueChainMomentStatus.in_progress,
                approvalStatus=DefineApprovalStatus.agreed,
            ),
        ]

        repaired = repair_moments(moments, [fallback], handoff=self.handoff)

        self.assertEqual(repaired, moments)

    def test_initial_ai_moment_merge_recovers_without_changing_other_fields(self) -> None:
        fallback = generate_define_state(self.handoff)
        target = fallback.moments[0]
        ai_moment = ValueChainMoment(
            name=target.name,
            evidenceIds=target.evidence_ids,
        )
        proposal = self._proposal(
            SingleOrganizingIdeaCandidate(statement="Care in motion"),
            moments=[ai_moment],
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(proposal),
        )

        self.assertEqual(state.moments[0].id, ai_moment.id)
        self.assertEqual(state.moments[0].question, target.question)
        self.assertEqual(state.moments[0].today, target.today)
        self.assertEqual(state.moments[0].desired_state, target.desired_state)
        self.assertEqual(state.moments[0].the_move, target.the_move)
        self.assertEqual(state.moments[0].status, target.status)
        self.assertEqual(state.soi_candidate.statement, "Care in motion")
        self.assertEqual(state.positioning.audience, "AI audience")

    def test_fallback_soi_and_positioning_use_role_matched_evidence(self) -> None:
        bad_positioning = self._evidence(
            "Today the organisation leads with Offer.",
            coverage_area_ids=["market_position"],
        )
        bad_social = self._evidence(
            "Contribution level: Charity - One-off giving.",
            coverage_area_ids=["social_contribution"],
        )
        category = self._evidence(
            (
                "A cooperative retail group serving local households through "
                "grocery stores."
            ),
            coverage_area_ids=["organisation_basics", "market_position"],
        )
        benefit = self._evidence(
            "Customers need dependable access to affordable everyday essentials.",
            coverage_area_ids=["customer_needs"],
        )
        reason = self._evidence(
            (
                "The organisation operates a nationwide store network with "
                "documented customer reach."
            ),
            coverage_area_ids=["performance_governance", "market_position"],
        )
        theme = self.handoff.brief.themes[0].model_copy(
            update={
                "name": "Employee experience",
                "summary": "evidence items clustered around staff experience",
                "evidence_count": 1,
                "evidence_ids": [bad_positioning.id],
            }
        )
        handoff = self.handoff.model_copy(
            update={
                "brief": self.handoff.brief.model_copy(
                    update={"themes": [theme], "strongest_evidence": []},
                    deep=True,
                ),
                "output": self.handoff.output.model_copy(
                    update={
                        "positioning_evidence": [
                            bad_positioning,
                            category,
                            benefit,
                            reason,
                        ],
                        "social_contribution_evidence": [bad_social],
                    },
                    deep=True,
                ),
                "strongest_evidence_ids": [
                    bad_positioning.id,
                    category.id,
                    benefit.id,
                    reason.id,
                ],
                "evidence_references": [
                    bad_positioning.id,
                    bad_social.id,
                    category.id,
                    benefit.id,
                    reason.id,
                ],
            },
            deep=True,
        )

        state = generate_define_state(handoff)

        self.assertEqual(
            state.positioning.category_context,
            "cooperative retail group serving local households through grocery stores",
        )
        self.assertEqual(
            state.positioning.capability_value,
            benefit.claim.rstrip("."),
        )
        self.assertEqual(
            state.positioning.reason_believability,
            reason.claim.rstrip("."),
        )
        self.assertEqual(
            state.positioning.provenance.status,
            EvidenceStatus.source_derived,
        )

    def test_unusable_ai_soi_candidates_use_synthesized_fallback(self) -> None:
        unsuitable = (
            "Dominant market share and claims ratio signals cost pressure.",
            "Regulatory risk could affect future governance and performance.",
            "Employee experience",
            (
                "Customers Getting a quote should feel reliable. Getting a quote "
                "may be a strength to preserve."
            ),
            "The organisation served 950,000 customers in 2025.",
        )
        for statement in unsuitable:
            with self.subTest(statement=statement):
                state = generate_define_state(
                    self.handoff,
                    ai_client=ProposalAIClient(
                        self._proposal(
                            SingleOrganizingIdeaCandidate(statement=statement)
                        )
                    ),
                )

                assert state.soi_candidate is not None
                self.assertNotEqual(state.soi_candidate.statement, statement)
                self.assertEqual(state.positioning.audience, "AI audience")

    def test_soi_synthesizes_multiple_cross_company_sources(self) -> None:
        identity = self._research(
            "Organisation Structure and Business Model",
            (
                "River Co-op is a producer-owned cooperative created for local "
                "grower benefit."
            ),
        )
        products = self._research(
            "Products and Producer Services",
            (
                "River Co-op supports local growers with shared distribution "
                "and practical business services."
            ),
        )
        customer = self._evidence(
            "Help local growers build secure livelihoods.",
            coverage_area_ids=["customer_needs", "purpose_driven_proof"],
        )
        handoff = self._soi_handoff(
            organisation="River Co-op",
            research=[identity, products],
            evidence=[customer],
        )

        state = generate_define_state(handoff)

        assert state.soi_candidate is not None
        self.assertEqual(
            state.soi_candidate.statement,
            (
                "Support local growers with shared distribution and practical "
                "business services"
            ),
        )
        self.assertEqual(
            state.soi_candidate.evidence_ids,
            [products.id, identity.id, customer.id],
        )
        self.assertTrue(
            set(state.soi_candidate.evidence_ids).issubset(
                set(state.evidence_references)
            )
        )
        self.assertIn("organisation identity", state.soi_candidate.meaning)
        self.assertIn("products and services", state.soi_candidate.meaning)
        self.assertNotIn("coverageAreaIds", state.soi_candidate.meaning)
        self.assertNotIn("Customers Getting", state.soi_candidate.meaning)
        source_texts = {identity.summary, products.summary, customer.claim}
        self.assertNotIn(state.soi_candidate.statement, source_texts)

    def test_sparse_soi_uses_a_supported_action_without_invented_facts(self) -> None:
        source = self._research(
            "Products and Services",
            "Northstar Studio helps rural households access reliable repairs.",
        )
        handoff = self._soi_handoff(
            organisation="Northstar Studio",
            research=[source],
            evidence=[],
        )

        state = generate_define_state(handoff)

        assert state.soi_candidate is not None
        self.assertEqual(
            state.soi_candidate.statement,
            "Help rural households access reliable repairs",
        )
        self.assertEqual(state.soi_candidate.evidence_ids, [source.id])
        self.assertIn("products and services", state.soi_candidate.meaning)
        self.assertNotIn("recurring", state.soi_candidate.meaning)

    def test_ai_template_positioning_fields_are_repaired_per_role(self) -> None:
        proposal = self._proposal(
            SingleOrganizingIdeaCandidate(statement="Care in motion"),
            positioning=PositioningStatement(
                audience="Customers",
                categoryContext="Employee experience",
                capabilityValue="Today the organisation leads with Offer.",
                reasonBelievability="Contribution level: Charity - One-off giving.",
                composedStatement="AI composed statement",
            ),
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(proposal),
        )

        self.assertEqual(state.positioning.audience, "Customers")
        self.assertNotEqual(state.positioning.category_context, "Employee experience")
        self.assertNotEqual(
            state.positioning.capability_value,
            "Today the organisation leads with Offer.",
        )
        self.assertNotEqual(
            state.positioning.reason_believability,
            "Contribution level: Charity - One-off giving.",
        )
        self.assertNotEqual(
            state.positioning.composed_statement,
            "AI composed statement",
        )

    def test_benefit_only_ai_reason_is_repaired_with_proof(self) -> None:
        outcome_statement = (
            "Adoption of digital tools improves customer experience and "
            "reduces administration."
        )
        proposal = self._proposal(
            SingleOrganizingIdeaCandidate(statement="Care in motion"),
            positioning=PositioningStatement(
                audience="Customers",
                categoryContext="service provider",
                capabilityValue="supports reliable daily operations",
                reasonBelievability=outcome_statement,
                composedStatement="AI composed statement",
            ),
        )

        state = generate_define_state(
            self.handoff,
            ai_client=ProposalAIClient(proposal),
        )

        self.assertEqual(state.positioning.category_context, "service provider")
        self.assertEqual(
            state.positioning.capability_value,
            "supports reliable daily operations",
        )
        self.assertNotEqual(
            state.positioning.reason_believability,
            outcome_statement,
        )

    def test_positioning_roles_use_distinct_cross_company_evidence(self) -> None:
        market_analysis = self._evidence(
            (
                "Dominant market share combined with a high claims-to-premium "
                "ratio signals pressure on affordability."
            ),
            coverage_area_ids=[
                "organisation_basics",
                "customer_needs",
                "market_position",
            ],
        )
        template = self._evidence(
            "Today the organisation leads with Offer.",
            coverage_area_ids=["organisation_basics", "market_position"],
        )
        identity = self._research(
            "Organisation Structure and Business Model",
            (
                "Harbour Mutual is a member-owned provider of insurance and "
                "financial wellbeing services."
            ),
        )
        benefit = self._research(
            "Products and Member Services",
            (
                "Harbour Mutual provides flexible cover and direct support "
                "that helps members recover from unexpected events."
            ),
        )
        proof = self._research(
            "Service Scale and Outcomes",
            (
                "Harbour Mutual paid 92% of accepted member claims within five "
                "working days through its nationwide service network."
            ),
        )
        theme = self.handoff.brief.themes[0].model_copy(
            update={"name": "Employee experience", "summary": "Staff theme"}
        )
        handoff = self.handoff.model_copy(
            update={
                "brief": self.handoff.brief.model_copy(
                    update={
                        "organisation_name": "Harbour Mutual",
                        "themes": [theme],
                        "strongest_evidence": [],
                    },
                    deep=True,
                ),
                "output": self.handoff.output.model_copy(
                    update={
                        "research_findings": [identity, benefit, proof],
                        "positioning_evidence": [market_analysis, template],
                        "social_contribution_evidence": [],
                    },
                    deep=True,
                ),
                "strongest_evidence_ids": [market_analysis.id],
                "evidence_references": [
                    market_analysis.id,
                    template.id,
                    identity.id,
                    benefit.id,
                    proof.id,
                ],
            },
            deep=True,
        )

        state = generate_define_state(handoff)

        self.assertEqual(
            state.positioning.category_context,
            "member-owned provider of insurance and financial wellbeing services",
        )
        self.assertEqual(
            state.positioning.capability_value,
            (
                "provides flexible cover and direct support that helps members "
                "recover from unexpected events"
            ),
        )
        self.assertEqual(
            state.positioning.reason_believability,
            proof.summary.rstrip("."),
        )
        self.assertNotEqual(
            state.positioning.category_context,
            state.positioning.capability_value,
        )
        self.assertNotEqual(state.positioning.category_context, theme.name)
        self.assertNotIn(market_analysis.claim, state.positioning.composed_statement)
        self.assertNotIn(template.claim, state.positioning.composed_statement)
        self.assertEqual(
            state.positioning.evidence_ids,
            [identity.id, benefit.id, proof.id],
        )

    def test_sparse_positioning_uses_supported_roles_without_inventing(self) -> None:
        identity = self._research(
            "Company and Sector",
            "Northstar Co-op is a member-owned energy retailer.",
        )
        benefit = self._evidence(
            "Provides households with reliable access to renewable electricity.",
            coverage_area_ids=["customer_needs"],
        )
        proof = self._evidence(
            "Its documented service network operates across 12 local districts.",
            coverage_area_ids=["performance_governance"],
        )
        handoff = self.handoff.model_copy(
            update={
                "brief": self.handoff.brief.model_copy(
                    update={
                        "organisation_name": "Northstar Co-op",
                        "themes": [],
                        "strongest_evidence": [],
                    },
                    deep=True,
                ),
                "output": self.handoff.output.model_copy(
                    update={
                        "research_findings": [identity],
                        "positioning_evidence": [benefit, proof],
                        "social_contribution_evidence": [],
                    },
                    deep=True,
                ),
                "strongest_evidence_ids": [],
                "evidence_references": [identity.id, benefit.id, proof.id],
            },
            deep=True,
        )

        state = generate_define_state(handoff)

        self.assertEqual(
            state.positioning.category_context,
            "member-owned energy retailer",
        )
        self.assertEqual(
            state.positioning.capability_value,
            benefit.claim.rstrip("."),
        )
        self.assertEqual(
            state.positioning.reason_believability,
            proof.claim.rstrip("."),
        )
        self.assertNotIn("Harbour Mutual", state.positioning.composed_statement)

    @staticmethod
    def _proposal(
        soi: SingleOrganizingIdeaCandidate | None,
        *,
        positioning: PositioningStatement | None = None,
        values: list[ValueCommitment] | None = None,
        moments: list[ValueChainMoment] | None = None,
    ) -> DefineProposal:
        return DefineProposal(
            soiCandidate=soi,
            positioning=positioning or PositioningStatement(audience="AI audience"),
            values=values or [ValueCommitment(name="AI commitment")],
            moments=moments or [ValueChainMoment(name="AI moment")],
        )

    @staticmethod
    def _evidence(
        claim: str,
        *,
        coverage_area_ids: list[str],
    ) -> IdentifyEvidence:
        return IdentifyEvidence(
            source=EvidenceSource(
                title="Regression evidence",
                source_type="identify-activity",
            ),
            claim=claim,
            sourceActivity="hot-seat",
            coverageAreaIds=coverage_area_ids,
            evidenceStatus=EvidenceStatus.user_confirmed,
        )

    def _soi_handoff(
        self,
        *,
        organisation: str,
        research: list[ResearchFinding],
        evidence: list[IdentifyEvidence],
    ):
        return self.handoff.model_copy(
            update={
                "brief": self.handoff.brief.model_copy(
                    update={
                        "organisation_name": organisation,
                        "themes": [],
                        "strongest_evidence": [],
                    },
                    deep=True,
                ),
                "output": self.handoff.output.model_copy(
                    update={
                        "company_cards_evidence": None,
                        "research_findings": research,
                        "positioning_evidence": evidence,
                        "social_contribution_evidence": [],
                    },
                    deep=True,
                ),
                "strongest_evidence_ids": [item.id for item in evidence],
                "evidence_references": [
                    *[item.id for item in research],
                    *[item.id for item in evidence],
                ],
            },
            deep=True,
        )

    @staticmethod
    def _research(topic: str, summary: str) -> ResearchFinding:
        return ResearchFinding(
            topic=topic,
            summary=summary,
            sourceType=ResearchSourceType.public_website,
            sourceLabel="Organisation website",
        )


if __name__ == "__main__":
    unittest.main()
