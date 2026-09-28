import json
import re
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    DefineApprovalStatus,
    DefineOutput,
    DefineProvenance,
    EvidenceStatus,
    StressTestCriterionResult,
    StressTestCriterionStatus,
    StressTestOutput,
    StressTestState,
    StressTestStatus,
    utc_now,
)
from app.services.ai_client import AIClient, AIClientError
from app.services.define_evidence import DefineEvidenceRecord


# Canonical source: CORE Playbook, section 3.5, "8 POINT STRESS TEST".
STRESS_TEST_CRITERIA = (
    ("credible", "CREDIBLE", "Is the SOI® based on reality, hard facts and evidence?"),
    (
        "resilient",
        "RESILIENT",
        "Will the SOI® be sustainable over the long-term regardless of "
        "management, technology and market changes?",
    ),
    (
        "relevant",
        "RELEVANT",
        "Will the SOI® deliver value to our business and stakeholders?",
    ),
    (
        "commercial",
        "COMMERCIAL",
        "Will alignment with the SOI® help ensure that our business thrives "
        "and maintains commercial success?",
    ),
    (
        "beneficial",
        "BENEFICIAL",
        "Will the adoption of the SOI® impact positively on people and the planet?",
    ),
    (
        "single",
        "SINGLE",
        "Will the SOI® provide the single-minded focus required to help "
        "separate what is important from what is not?",
    ),
    (
        "organizing",
        "ORGANIZING",
        "Will each function of the business and the wider ecosystem be able "
        "to self-organise their alignment and contribution to the SOI®?",
    ),
    (
        "idea",
        "IDEA",
        "Is the SOI® a compelling concept that people internally and "
        "externally will admire and aspire to be a part of?",
    ),
)
OVERARCHING_QUESTION = (
    "Will this SOI® help the organisation thrive while making a positive "
    "contribution to society?"
)
LEGACY_REASONING = (
    "The agreed Define output and linked evidence provide material for human "
    "review against this criterion."
)
LEGACY_NO_EVIDENCE_REASONING = (
    "No linked evidence is available to assess this criterion."
)
LEGACY_NO_EVIDENCE_CONCERN = (
    "Evidence is insufficient for a defensible conclusion."
)
MAX_EVIDENCE_PER_CRITERION = 8
LEGACY_QUESTION_VARIANTS = {
    "relevant": {
        "Will the SOI® deliver value to our business and our stakeholders?",
    }
}


@dataclass(frozen=True)
class CriterionEvidenceGuide:
    coverage: frozenset[str]
    terms: tuple[str, ...]
    evidence_focus: str
    unresolved_test: str


@dataclass(frozen=True)
class EvidenceTheme:
    label: str
    coverage: frozenset[str] = frozenset()
    terms: tuple[str, ...] = ()


CRITERION_GUIDES = {
    "credible": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "organisation_basics",
                "founding_story",
                "performance_governance",
                "evidence_sources",
                "purpose_driven_proof",
            }
        ),
        terms=(
            "founded",
            "identity",
            "governance",
            "evidence",
            "rating",
            "trusted",
            "claims",
            "member benefit",
            "not-for-profit",
            "products",
            "services",
        ),
        evidence_focus=(
            "organisational reality, demonstrated behaviour and factual proof"
        ),
        unresolved_test=(
            "whether the documented facts are sufficient proof of the SOI in practice"
        ),
    ),
    "resilient": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "vulnerabilities",
                "political_context",
                "economic_context",
                "social_context",
                "technological_context",
                "technology_context",
                "legal_context",
                "environmental_context",
                "performance_governance",
            }
        ),
        terms=(
            "long-term",
            "regulatory",
            "legislation",
            "technology",
            "market",
            "pressure",
            "risk",
            "reserves",
            "sustainable",
            "adapt",
            "change",
        ),
        evidence_focus="long-term pressures, vulnerabilities and capacity to adapt",
        unresolved_test=(
            "whether the SOI remains durable through the identified changes and "
            "pressures"
        ),
    ),
    "relevant": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "customer_needs",
                "employee_experience",
                "people_planet_stakeholders",
                "partner_supplier_context",
                "market_position",
            }
        ),
        terms=(
            "customer",
            "member",
            "employee",
            "stakeholder",
            "need",
            "experience",
            "service",
            "journey",
            "access",
            "retention",
            "value",
        ),
        evidence_focus="stakeholder needs, experiences and value delivered",
        unresolved_test=(
            "whether the SOI is relevant across all material stakeholder groups"
        ),
    ),
    "commercial": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "economic_context",
                "market_position",
                "performance_governance",
                "organisation_basics",
            }
        ),
        terms=(
            "financial",
            "commercial",
            "revenue",
            "premium",
            "claims ratio",
            "cost",
            "market share",
            "surplus",
            "reserve",
            "operating",
            "affordability",
            "deficit",
        ),
        evidence_focus=(
            "financial sustainability, operating performance and market viability"
        ),
        unresolved_test=(
            "whether purpose alignment can be sustained alongside commercial "
            "constraints"
        ),
    ),
    "beneficial": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "social_contribution",
                "people_planet_stakeholders",
                "social_context",
                "environmental_context",
                "customer_needs",
            }
        ),
        terms=(
            "wellbeing",
            "community",
            "social",
            "health",
            "people",
            "planet",
            "environment",
            "charitable",
            "member benefit",
            "positive",
        ),
        evidence_focus=(
            "effects on members, communities, wider society and the environment"
        ),
        unresolved_test=(
            "whether positive impact is demonstrated for both people and planet"
        ),
    ),
    "single": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "organisation_basics",
                "founding_story",
                "market_position",
                "purpose_driven_proof",
            }
        ),
        terms=(
            "purpose",
            "focus",
            "priority",
            "identity",
            "member-first",
            "member focused",
            "wellbeing",
            "theme",
            "trade-off",
        ),
        evidence_focus=(
            "recurring purpose themes and evidence of a clear decision focus"
        ),
        unresolved_test=(
            "whether competing priorities can be resolved consistently through one idea"
        ),
    ),
    "organizing": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "employee_experience",
                "performance_governance",
                "partner_supplier_context",
                "people_planet_stakeholders",
                "customer_needs",
            }
        ),
        terms=(
            "employee",
            "team",
            "function",
            "governance",
            "partner",
            "provider",
            "ecosystem",
            "operation",
            "decision",
            "service",
            "journey",
        ),
        evidence_focus=(
            "operational decisions, functions, partners and stakeholder touchpoints"
        ),
        unresolved_test=(
            "whether every function and ecosystem partner can translate the SOI into "
            "action"
        ),
    ),
    "idea": CriterionEvidenceGuide(
        coverage=frozenset(
            {
                "founding_story",
                "market_position",
                "best_work",
                "purpose_driven_proof",
                "organisation_basics",
            }
        ),
        terms=(
            "purpose",
            "founding",
            "identity",
            "brand",
            "trusted",
            "distinct",
            "aspire",
            "admire",
            "member-first",
            "member focused",
            "wellbeing",
            "reputation",
        ),
        evidence_focus="identity, distinctiveness and stakeholder resonance",
        unresolved_test=(
            "whether the concept is distinctive and compelling beyond familiar purpose "
            "language"
        ),
    ),
}

CRITERION_EVIDENCE_THEMES = {
    "credible": (
        EvidenceTheme(
            "organisational identity and operating reality",
            frozenset({"organisation_basics", "founding_story"}),
        ),
        EvidenceTheme(
            "governance and documented performance",
            frozenset({"performance_governance", "evidence_sources"}),
            ("governance", "rating", "verified", "claims"),
        ),
        EvidenceTheme(
            "demonstrated purpose-led activity",
            frozenset({"purpose_driven_proof"}),
        ),
    ),
    "resilient": (
        EvidenceTheme(
            "regulatory and policy obligations",
            frozenset({"political_context", "legal_context"}),
            ("regulatory", "legislation"),
        ),
        EvidenceTheme(
            "technology change and digital service development",
            frozenset({"technology_context", "technological_context"}),
            ("technology", "digital", "app"),
        ),
        EvidenceTheme(
            "economic, market and operating pressures",
            frozenset({"economic_context", "market_position", "vulnerabilities"}),
            ("market", "pressure", "risk", "cost"),
        ),
    ),
    "relevant": (
        EvidenceTheme(
            "member and customer needs",
            frozenset({"customer_needs"}),
            ("customer", "member", "need"),
        ),
        EvidenceTheme(
            "service experiences and stakeholder touchpoints",
            frozenset({"best_work", "employee_experience"}),
            ("service", "experience", "journey", "access"),
        ),
        EvidenceTheme(
            "partner and wider stakeholder context",
            frozenset({"partner_supplier_context", "people_planet_stakeholders"}),
            ("partner", "stakeholder"),
        ),
    ),
    "commercial": (
        EvidenceTheme(
            "financial and claims performance",
            frozenset({"economic_context", "performance_governance"}),
            ("financial", "premium", "claims", "cost", "reserve"),
        ),
        EvidenceTheme(
            "member scale and market position",
            frozenset({"market_position", "organisation_basics"}),
            ("member", "market share", "scale"),
        ),
        EvidenceTheme(
            "operating sustainability",
            terms=("operating", "sustainable", "affordability"),
        ),
    ),
    "beneficial": (
        EvidenceTheme(
            "member wellbeing and healthcare access",
            frozenset({"customer_needs", "people_planet_stakeholders"}),
            ("wellbeing", "health", "access", "member benefit"),
        ),
        EvidenceTheme(
            "community and social contribution",
            frozenset({"social_contribution", "social_context"}),
            ("community", "social", "charitable"),
        ),
        EvidenceTheme(
            "environmental context",
            frozenset({"environmental_context"}),
            ("climate", "environmental", "planet"),
        ),
    ),
    "single": (
        EvidenceTheme(
            "recurring purpose and identity themes",
            frozenset({"organisation_basics", "founding_story", "purpose_driven_proof"}),
            ("purpose", "identity", "member focused", "member-first"),
        ),
        EvidenceTheme(
            "positioning and organisational priorities",
            frozenset({"market_position"}),
            ("focus", "priority", "trade-off"),
        ),
    ),
    "organizing": (
        EvidenceTheme(
            "employee and functional context",
            frozenset({"employee_experience", "performance_governance"}),
            ("employee", "team", "function", "governance"),
        ),
        EvidenceTheme(
            "partner and ecosystem relationships",
            frozenset({"partner_supplier_context", "people_planet_stakeholders"}),
            ("partner", "provider", "ecosystem"),
        ),
        EvidenceTheme(
            "service delivery and stakeholder touchpoints",
            frozenset({"customer_needs", "best_work"}),
            ("service", "journey", "operation", "decision"),
        ),
    ),
    "idea": (
        EvidenceTheme(
            "founding purpose and organisational identity",
            frozenset({"founding_story", "organisation_basics", "purpose_driven_proof"}),
            ("purpose", "founding", "identity"),
        ),
        EvidenceTheme(
            "trust, reputation and stakeholder resonance",
            frozenset({"best_work", "people_planet_stakeholders"}),
            ("trusted", "reputation", "aspire", "admire"),
        ),
        EvidenceTheme(
            "market distinctiveness",
            frozenset({"market_position"}),
            ("distinct", "brand"),
        ),
    ),
}


class StressTestCriterionProposal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    criterion_id: str = Field(min_length=1, alias="criterionId")
    question: str = Field(min_length=1)
    status: StressTestCriterionStatus
    reasoning: str = Field(min_length=1)
    concerns: list[str] = Field(default_factory=list)
    suggested_refinement: str | None = Field(
        default=None,
        alias="suggestedRefinement",
    )
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")


class StressTestProposal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    criteria: list[StressTestCriterionProposal]


def evaluate_stress_test(
    assessment_id: UUID,
    define_output: DefineOutput,
    *,
    evidence_records: dict[UUID, DefineEvidenceRecord] | None = None,
    ai_client: AIClient | None = None,
) -> StressTestState:
    evidence = list(dict.fromkeys(define_output.evidence_references))
    records = evidence_records or {}
    selected = {
        criterion_id: _select_evidence(
            criterion_id,
            define_output,
            evidence,
            records,
        )
        for criterion_id, _, _ in STRESS_TEST_CRITERIA
    }
    proposal = _ai_proposal(define_output, selected, ai_client)
    used_ai = proposal is not None
    if proposal is None:
        proposal = _fallback_proposal(selected, define_output)

    now = utc_now()
    provenance = DefineProvenance(
        status=(
            EvidenceStatus.ai_inferred if used_ai else EvidenceStatus.source_derived
        ),
        rationale=(
            "Criterion-specific Stress Test synthesis generated from bounded "
            "agreed Define evidence."
            if used_ai
            else "Deterministic criterion-specific synthesis from bounded agreed "
            "Define evidence."
        ),
        generatedAt=now,
        sourceHandoff="structured_outputs.define.handoff",
    )
    proposal_by_id = {item.criterion_id: item for item in proposal.criteria}
    criteria = []
    for criterion_id, name, question in STRESS_TEST_CRITERIA:
        item = proposal_by_id[criterion_id]
        criteria.append(
            StressTestCriterionResult(
                criterionId=criterion_id,
                name=name,
                question=question,
                status=item.status,
                reasoning=item.reasoning,
                supportingEvidenceIds=item.evidence_ids,
                concerns=item.concerns,
                suggestedRefinement=item.suggested_refinement,
                provenance=provenance.model_copy(deep=True),
                approvalStatus=DefineApprovalStatus.ai_proposed,
            )
        )
    return StressTestState(
        assessmentId=assessment_id,
        status=StressTestStatus.ready_for_review,
        criteria=criteria,
        overarchingQuestion=OVERARCHING_QUESTION,
        evidenceReferences=evidence,
        provenance=provenance,
    )


def recover_legacy_stress_test(
    state: StressTestState,
    define_output: DefineOutput,
    *,
    evidence_records: dict[UUID, DefineEvidenceRecord],
    ai_client: AIClient | None = None,
) -> StressTestState:
    selected = {
        criterion_id: _select_evidence(
            criterion_id,
            define_output,
            list(dict.fromkeys(define_output.evidence_references)),
            evidence_records,
        )
        for criterion_id, _, _ in STRESS_TEST_CRITERIA
    }
    legacy_ids = {
        item.criterion_id
        for item in state.criteria
        if is_legacy_scaffold_criterion(item, state.evidence_references)
    }
    previous_fallback_ids = {
        item.criterion_id
        for item in state.criteria
        if _is_previous_fallback_criterion(
            item,
            define_output,
            selected.get(item.criterion_id, []),
        )
    }
    if not legacy_ids and not previous_fallback_ids:
        return state

    replacements: dict[str, StressTestCriterionResult] = {}
    generated = None
    if legacy_ids:
        generated = evaluate_stress_test(
            state.assessment_id or UUID(int=0),
            define_output,
            evidence_records=evidence_records,
            ai_client=ai_client,
        )
        replacements = {item.criterion_id: item for item in generated.criteria}

    fallback = _fallback_proposal(selected, define_output)
    fallback_by_id = {item.criterion_id: item for item in fallback.criteria}
    recovered = state.model_copy(deep=True)
    recovered.criteria = []
    for item in state.criteria:
        if item.criterion_id in legacy_ids and item.criterion_id in replacements:
            recovered.criteria.append(replacements[item.criterion_id])
        elif item.criterion_id in previous_fallback_ids:
            recovered.criteria.append(
                item.model_copy(
                    update={
                        "reasoning": fallback_by_id[item.criterion_id].reasoning,
                    },
                    deep=True,
                )
            )
        else:
            recovered.criteria.append(item)
    if generated is not None:
        recovered.provenance = generated.provenance
    return recovered


def _is_previous_fallback_criterion(
    criterion: StressTestCriterionResult,
    define_output: DefineOutput,
    records: list[DefineEvidenceRecord],
) -> bool:
    if (
        criterion.approval_status != DefineApprovalStatus.ai_proposed
        or criterion.provenance.status != EvidenceStatus.source_derived
        or criterion.provenance.rationale
        != "Deterministic criterion-specific synthesis from bounded agreed Define evidence."
    ):
        return False
    guide = CRITERION_GUIDES.get(criterion.criterion_id)
    if guide is None:
        return False
    return (
        criterion.reasoning
        == _previous_fallback_reasoning(define_output, records, guide)
        and criterion.supporting_evidence_ids == [item.id for item in records]
        and criterion.concerns
        == _fallback_concerns(criterion.criterion_id, records, guide)
        and criterion.suggested_refinement is None
    )


def _previous_fallback_reasoning(
    define_output: DefineOutput,
    records: list[DefineEvidenceRecord],
    guide: CriterionEvidenceGuide,
) -> str:
    soi = _agreed_soi_label(define_output)
    if not records:
        return (
            f'The agreed SOI "{soi}" cannot yet be assessed for '
            f"{guide.evidence_focus}: no resolved evidence in the Define handoff "
            "specifically addresses this criterion."
        )
    labels = [_legacy_evidence_label(item) for item in records[:3]]
    return (
        f'The agreed SOI "{soi}" has a grounded basis for review against '
        f"{guide.evidence_focus}. Evidence about {_join_phrases(labels)} is relevant, "
        "while human judgement is still required to determine "
        f"{guide.unresolved_test}."
    )


def is_legacy_scaffold_criterion(
    criterion: StressTestCriterionResult,
    evidence_references: list[UUID],
) -> bool:
    expected = next(
        (
            (name, question)
            for criterion_id, name, question in STRESS_TEST_CRITERIA
            if criterion_id == criterion.criterion_id
        ),
        None,
    )
    if (
        expected is None
        or criterion.approval_status != DefineApprovalStatus.ai_proposed
    ):
        return False
    has_evidence = bool(evidence_references)
    return (
        criterion.name == expected[0]
        and criterion.question
        in {expected[1], *LEGACY_QUESTION_VARIANTS.get(criterion.criterion_id, set())}
        and criterion.status
        == (
            StressTestCriterionStatus.needs_review
            if has_evidence
            else StressTestCriterionStatus.insufficient_evidence
        )
        and criterion.reasoning
        == (LEGACY_REASONING if has_evidence else LEGACY_NO_EVIDENCE_REASONING)
        and criterion.supporting_evidence_ids == evidence_references
        and criterion.concerns
        == ([] if has_evidence else [LEGACY_NO_EVIDENCE_CONCERN])
        and criterion.suggested_refinement is None
        and criterion.provenance.rationale
        == "Deterministic framework initialized from the agreed Define handoff."
    )


def build_stress_test_output(state: StressTestState) -> StressTestOutput:
    return StressTestOutput(
        criteria=state.criteria,
        overarchingQuestion=state.overarching_question,
        overarchingResponse=state.overarching_response,
        evidenceReferences=state.evidence_references,
        completedAt=utc_now() if state.status == StressTestStatus.completed else None,
    )


def _select_evidence(
    criterion_id: str,
    define_output: DefineOutput,
    allowed_ids: list[UUID],
    records: dict[UUID, DefineEvidenceRecord],
) -> list[DefineEvidenceRecord]:
    guide = CRITERION_GUIDES[criterion_id]
    allowed = set(allowed_ids)
    direct = set(_direct_evidence_ids(criterion_id, define_output))
    ranked: list[tuple[int, str, DefineEvidenceRecord]] = []

    for evidence_id in allowed:
        record = records.get(evidence_id)
        if record is None:
            continue
        score = _evidence_relevance_score(record, guide)
        if evidence_id in direct:
            score += 100
        if score > 0:
            ranked.append((score, str(evidence_id), record))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:MAX_EVIDENCE_PER_CRITERION]]


def _direct_evidence_ids(
    criterion_id: str,
    define_output: DefineOutput,
) -> list[UUID]:
    soi_ids = (
        define_output.agreed_soi.evidence_ids if define_output.agreed_soi else []
    )
    positioning_ids = (
        define_output.agreed_positioning.evidence_ids
        if define_output.agreed_positioning
        else []
    )
    value_ids = [
        evidence_id
        for value in define_output.agreed_values
        for evidence_id in value.evidence_ids
    ]
    moment_ids = [
        evidence_id
        for moment in define_output.agreed_moments
        for evidence_id in moment.evidence_ids
    ]
    if criterion_id == "credible":
        return _unique_ids([*soi_ids, *positioning_ids])
    if criterion_id == "relevant":
        return _unique_ids([*soi_ids, *positioning_ids, *moment_ids])
    if criterion_id == "commercial":
        return _unique_ids([*positioning_ids, *value_ids])
    if criterion_id == "beneficial":
        return _unique_ids([*soi_ids, *value_ids])
    if criterion_id == "single":
        return _unique_ids(soi_ids)
    if criterion_id == "organizing":
        return _unique_ids([*value_ids, *moment_ids])
    if criterion_id == "idea":
        return _unique_ids([*soi_ids, *value_ids])
    return []


def _evidence_relevance_score(
    record: DefineEvidenceRecord,
    guide: CriterionEvidenceGuide,
) -> int:
    coverage_score = 10 * len(guide.coverage.intersection(record.coverage_area_ids))
    searchable = " ".join(
        value
        for value in (
            record.title,
            record.summary or "",
            record.text,
            record.source_activity or "",
        )
        if value
    ).lower()
    term_score = sum(1 for term in guide.terms if term in searchable)
    return coverage_score + term_score


def _ai_proposal(
    define_output: DefineOutput,
    selected: dict[str, list[DefineEvidenceRecord]],
    ai_client: AIClient | None,
) -> StressTestProposal | None:
    if ai_client is None:
        return None
    payload = []
    for criterion_id, _, question in STRESS_TEST_CRITERIA:
        payload.append(
            {
                "criterionId": criterion_id,
                "question": question,
                "agreedDefineContext": _criterion_define_context(
                    criterion_id,
                    define_output,
                ),
                "evidence": [
                    item.prompt_payload() for item in selected[criterion_id]
                ],
            }
        )
    try:
        proposal = ai_client.generate_structured(
            prompt=(
                "Evaluate each fixed CORE criterion against only its supplied "
                "evidence and the agreed Define output. Return concise reasoning, "
                "genuine concerns, and a refinement only when warranted. Use "
                "insufficient-evidence when the supplied evidence cannot support a "
                "defensible review. Do not score.\n\n"
                "Criterion contexts: "
                f"{json.dumps(payload, default=str)}"
            ),
            output_schema=StressTestProposal,
            system=(
                "You perform evidence-grounded SOI Stress Test synthesis. Preserve "
                "the supplied criterion IDs and questions. Use only supplied evidence "
                "IDs, never invent evidence or mark human approval."
            ),
        )
        _validate_ai_proposal(proposal, selected)
        return proposal
    except (AIClientError, ValueError):
        return None


def _validate_ai_proposal(
    proposal: StressTestProposal,
    selected: dict[str, list[DefineEvidenceRecord]],
) -> None:
    expected = [(item[0], item[2]) for item in STRESS_TEST_CRITERIA]
    actual = [(item.criterion_id, item.question) for item in proposal.criteria]
    if actual != expected:
        raise ValueError("Stress Test proposal must preserve all fixed CORE criteria.")
    for item in proposal.criteria:
        allowed = {record.id for record in selected[item.criterion_id]}
        if not set(item.evidence_ids).issubset(allowed):
            raise ValueError("Stress Test proposal contains unknown evidence IDs.")
        if (
            item.status != StressTestCriterionStatus.insufficient_evidence
            and not item.evidence_ids
        ):
            raise ValueError("Stress Test conclusions require criterion evidence.")
        if not item.reasoning.strip() or any(
            not concern.strip() for concern in item.concerns
        ):
            raise ValueError("Stress Test narrative fields must not be blank.")
        if (
            item.suggested_refinement is not None
            and not item.suggested_refinement.strip()
        ):
            raise ValueError("Stress Test refinements must not be blank.")


def _fallback_proposal(
    selected: dict[str, list[DefineEvidenceRecord]],
    define_output: DefineOutput,
) -> StressTestProposal:
    criteria = []
    for criterion_id, _, question in STRESS_TEST_CRITERIA:
        records = selected[criterion_id]
        guide = CRITERION_GUIDES[criterion_id]
        soi = _agreed_soi_label(define_output)
        if not records:
            criteria.append(
                StressTestCriterionProposal(
                    criterionId=criterion_id,
                    question=question,
                    status=StressTestCriterionStatus.insufficient_evidence,
                    reasoning=(
                        f'The agreed SOI "{soi}" cannot yet be assessed for '
                        f"{guide.evidence_focus}: no resolved evidence in the "
                        "Define handoff specifically addresses this criterion."
                    ),
                    concerns=[
                        f"Evidence is needed to determine {guide.unresolved_test}."
                    ],
                    evidenceIds=[],
                )
            )
            continue

        themes = _evidence_themes(criterion_id, records)
        concerns = _fallback_concerns(criterion_id, records, guide)
        criteria.append(
            StressTestCriterionProposal(
                criterionId=criterion_id,
                question=question,
                status=StressTestCriterionStatus.needs_review,
                reasoning=(
                    f'For the agreed SOI "{soi}", selected evidence concerning '
                    f"{_join_phrases(themes)} provides a grounded basis to review "
                    f"{guide.evidence_focus}. The evidence supports review of this "
                    "criterion, but human judgement is still required to determine "
                    f"{guide.unresolved_test}."
                ),
                concerns=concerns,
                evidenceIds=[item.id for item in records],
            )
        )
    return StressTestProposal(criteria=criteria)


def _criterion_define_context(
    criterion_id: str,
    define_output: DefineOutput,
) -> dict[str, object]:
    context: dict[str, object] = {
        "agreedSoi": (
            define_output.agreed_soi.statement if define_output.agreed_soi else None
        )
    }
    if criterion_id in {"credible", "relevant", "commercial", "single", "idea"}:
        positioning = define_output.agreed_positioning
        context["agreedPositioning"] = (
            positioning.composed_statement if positioning else None
        )
    if criterion_id in {"beneficial", "single", "organizing", "idea"}:
        context["agreedValues"] = [
            {"name": item.name, "meaning": item.meaning}
            for item in define_output.agreed_values
        ]
    if criterion_id in {"relevant", "organizing"}:
        context["agreedMomentsOfTruth"] = [
            {
                "name": item.name,
                "today": item.today,
                "desiredState": item.desired_state,
                "theMove": item.the_move,
            }
            for item in define_output.agreed_moments
        ]
    if define_output.unresolved_questions:
        context["relevantUnresolvedQuestions"] = define_output.unresolved_questions
    return context


def _agreed_soi_label(define_output: DefineOutput) -> str:
    if define_output.agreed_soi is None:
        return "the agreed Define proposition"
    return define_output.agreed_soi.statement


def _fallback_concerns(
    criterion_id: str,
    records: list[DefineEvidenceRecord],
    guide: CriterionEvidenceGuide,
) -> list[str]:
    searchable = " ".join(
        " ".join(
            value
            for value in (record.title, record.summary or "", record.text)
            if value
        )
        for record in records
    ).lower()
    if criterion_id == "beneficial" and not any(
        term in searchable for term in ("planet", "environment", "climate")
    ):
        return [
            "People and community evidence is present, but evidence of planet or "
            "environmental benefit is limited."
        ]
    if criterion_id == "organizing" and not any(
        term in searchable for term in ("function", "ecosystem")
    ):
        return [
            "Evidence showing how functions and ecosystem partners would translate "
            "the SOI into action is limited."
        ]
    return [
        "The selected evidence does not by itself establish "
        f"{guide.unresolved_test}."
    ]


def _evidence_themes(
    criterion_id: str,
    records: list[DefineEvidenceRecord],
) -> list[str]:
    themes = []
    for theme in CRITERION_EVIDENCE_THEMES[criterion_id]:
        if any(_record_supports_theme(record, theme) for record in records):
            themes.append(theme.label)
    if themes:
        return themes[:3]
    return [CRITERION_GUIDES[criterion_id].evidence_focus]


def _record_supports_theme(
    record: DefineEvidenceRecord,
    theme: EvidenceTheme,
) -> bool:
    if theme.coverage.intersection(record.coverage_area_ids):
        return True
    searchable = " ".join(
        value
        for value in (record.title, record.summary or "", record.text)
        if value
    ).lower()
    return any(term in searchable for term in theme.terms)


def _legacy_evidence_label(record: DefineEvidenceRecord) -> str:
    value = record.summary or record.title
    value = re.sub(
        r"\s*\((?:correct|interesting|investigate|wrong)\)\s*$",
        "",
        value,
    )
    value = value.replace("_", " ").strip().rstrip(".")
    if len(value) <= 90:
        return value
    words = value.split()
    shortened = " ".join(words[:12])
    return f"{shortened.rstrip('.,;:')}..."


def _join_phrases(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return f"{', '.join(phrases[:-1])}, and {phrases[-1]}"


def _unique_ids(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))
