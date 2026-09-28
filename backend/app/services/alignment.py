from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import (
    AdoptedAction,
    AlignmentFindingStatus,
    AlignmentGap,
    AlignmentItemStatus,
    AlignmentOutput,
    AlignmentState,
    AlignmentStatus,
    DecisionCanvas,
    DecisionCanvasStatus,
    DefineOutput,
    DefineProvenance,
    EvidenceStatus,
    FunctionAlignment,
    PriorityAction,
    ProgressSnapshot,
    StressTestOutput,
    SuggestedMove,
    ValueGateResult,
    utc_now,
)
from app.services.ai_client import AIClient, AIClientError


ALIGNMENT_HANDOFF = "structured_outputs.define+structured_outputs.stress_test"


class AlignmentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    functional_alignment: list[FunctionAlignment] = Field(default_factory=list, alias="functionalAlignment")
    gaps: list[AlignmentGap] = Field(default_factory=list)
    priority_actions: list[PriorityAction] = Field(default_factory=list, alias="priorityActions")
    unresolved_questions: list[str] = Field(default_factory=list, alias="unresolvedQuestions")


class DecisionReframeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reframed_question: str = Field(min_length=1, alias="reframedQuestion")
    reasoning: str = Field(min_length=1)


def initialize_alignment(
    assessment_id: UUID,
    define_output: DefineOutput,
    stress_output: StressTestOutput,
    ai_client: AIClient | None = None,
) -> AlignmentState:
    evidence_ids = _unique_ids(
        [*define_output.evidence_references, *stress_output.evidence_references]
    )
    proposal = _generate_proposal(define_output, stress_output, ai_client)
    _validate_proposal(proposal, evidence_ids)
    now = utc_now()
    provenance = DefineProvenance(
        status=EvidenceStatus.ai_inferred,
        rationale="Alignment proposal derived from the completed Define and Stress Test outputs.",
        generatedAt=now,
        sourceHandoff=ALIGNMENT_HANDOFF,
    )
    state = AlignmentState(
        assessmentId=assessment_id,
        status=AlignmentStatus.in_progress,
        functionalAlignment=proposal.functional_alignment,
        gaps=proposal.gaps,
        priorityActions=proposal.priority_actions,
        unresolvedQuestions=proposal.unresolved_questions,
        evidenceReferences=evidence_ids,
        provenance=provenance,
        updatedAt=now,
    )
    _link_alignment_items(state)
    state.progress_snapshots.append(
        ProgressSnapshot(
            outstandingActionIds=[item.id for item in state.priority_actions],
            unresolvedGapIds=[item.id for item in state.gaps],
            observations=["Alignment initialized from the completed cross-stage handoff."],
            evidenceReferences=evidence_ids,
        )
    )
    state.output = build_alignment_output(state)
    return state


def build_alignment_output(state: AlignmentState) -> AlignmentOutput:
    return AlignmentOutput(
        functionalAlignment=state.functional_alignment,
        gaps=state.gaps,
        priorityActions=state.priority_actions,
        decisions=state.decisions,
        adoptedActions=state.adopted_actions,
        progressSnapshots=state.progress_snapshots,
        unresolvedQuestions=state.unresolved_questions,
        evidenceReferences=state.evidence_references,
        sourceDefineOutput=state.source_define_output,
        sourceStressTestOutput=state.source_stress_test_output,
        provenance=state.provenance,
        updatedAt=state.updated_at,
    )


def reframe_decision(
    decision: DecisionCanvas,
    define_output: DefineOutput,
    stress_output: StressTestOutput,
    ai_client: AIClient | None,
) -> DecisionCanvas:
    proposal = None
    if ai_client is not None:
        try:
            proposal = ai_client.generate_structured(
                prompt=(
                    "Reframe the user's decision into a clear strategic question without "
                    "changing or answering it. Use only this context:\n"
                    f"Original: {decision.original_question}\n"
                    f"Define: {define_output.model_dump_json(by_alias=True)}\n"
                    f"Stress Test: {stress_output.model_dump_json(by_alias=True)}"
                ),
                output_schema=DecisionReframeProposal,
                system=(
                    "You support a PurpOS Decision Canvas. Preserve the user's original "
                    "question, do not invent evidence, scores, percentages, or adoption."
                ),
            )
        except AIClientError:
            proposal = None
    if proposal is None:
        soi = define_output.agreed_soi.statement if define_output.agreed_soi else "the agreed SOI"
        proposal = DecisionReframeProposal(
            reframedQuestion=(
                f"How should we approach '{decision.original_question}' so the decision "
                f"is consistent with {soi}?"
            ),
            reasoning="Frames the decision against the agreed purpose without changing the original question.",
        )
    return decision.model_copy(
        update={
            "reframed_question": proposal.reframed_question,
            "reframe_reasoning": proposal.reasoning,
            "status": DecisionCanvasStatus.reframed,
            "updated_at": utc_now(),
            "provenance": _ai_provenance("Decision reframe based on the canonical Alignment handoff."),
        },
        deep=True,
    )


def evaluate_decision(
    decision: DecisionCanvas,
    define_output: DefineOutput,
    stress_output: StressTestOutput,
) -> DecisionCanvas:
    gates: list[ValueGateResult] = []
    if define_output.agreed_soi is not None:
        gates.append(_gate("soi", "define.soi", define_output.agreed_soi.statement or "SOI", define_output.agreed_soi.evidence_ids))
    if define_output.agreed_positioning is not None:
        gates.append(_gate("positioning", "define.positioning", define_output.agreed_positioning.composed_statement or "Positioning Statement", define_output.agreed_positioning.evidence_ids))
    for value in define_output.agreed_values:
        gates.append(_gate(f"value:{value.id}", f"define.values.{value.id}", value.name, value.evidence_ids))
    for moment in define_output.agreed_moments:
        gates.append(_gate(f"moment:{moment.id}", f"define.moments.{moment.id}", moment.name, moment.evidence_ids))
    for criterion in stress_output.criteria:
        tensions = criterion.concerns or ([criterion.suggested_refinement] if criterion.suggested_refinement else [])
        gates.append(
            ValueGateResult(
                gateId=f"stress:{criterion.criterion_id}",
                frameworkReference=f"stress_test.criteria.{criterion.criterion_id}",
                frameworkLabel=criterion.name,
                status=(AlignmentFindingStatus.aligned if criterion.status == "supported" else AlignmentFindingStatus.tension),
                reasoning=criterion.reasoning,
                supportingEvidenceIds=criterion.supporting_evidence_ids,
                tensions=tensions,
                provenance=criterion.provenance,
            )
        )
    moves = [
        SuggestedMove(
            action=gate.tensions[0],
            rationale=f"Address the recorded tension against {gate.framework_label}.",
            relatedGateId=gate.gate_id,
            relatedDecisionId=decision.id,
            evidenceReferences=gate.supporting_evidence_ids,
            provenance=_ai_provenance("Proposed from a reviewed Value Gate tension; user adoption is required."),
        )
        for gate in gates
        if gate.tensions
    ]
    evidence = _unique_ids([item for gate in gates for item in gate.supporting_evidence_ids])
    return decision.model_copy(
        update={
            "value_gates": gates,
            "suggested_moves": moves,
            "evidence_references": evidence,
            "status": DecisionCanvasStatus.evaluated,
            "updated_at": utc_now(),
        },
        deep=True,
    )


def adopt_move(move: SuggestedMove) -> tuple[SuggestedMove, AdoptedAction]:
    updated = move.model_copy(
        update={"adopted": True, "status": AlignmentItemStatus.adopted}, deep=True
    )
    action = AdoptedAction(
        sourceMoveId=move.id,
        decisionId=move.related_decision_id,
        action=move.action,
        rationale=move.rationale,
        evidenceReferences=move.evidence_references,
        provenance=DefineProvenance(
            status=EvidenceStatus.user_confirmed,
            rationale="User explicitly adopted an AI-proposed move.",
            updatedAt=utc_now(),
            sourceHandoff=ALIGNMENT_HANDOFF,
        ),
    )
    return updated, action


def _generate_proposal(define_output: DefineOutput, stress_output: StressTestOutput, ai_client: AIClient | None) -> AlignmentProposal:
    if ai_client is not None:
        try:
            return ai_client.generate_structured(
                prompt=(
                    "Propose qualitative functional alignment findings, evidence-supported gaps, "
                    "and ordered priority actions from these completed outputs. Do not score.\n"
                    f"Define: {define_output.model_dump_json(by_alias=True)}\n"
                    f"Stress Test: {stress_output.model_dump_json(by_alias=True)}"
                ),
                output_schema=AlignmentProposal,
                system=(
                    "Use only supplied evidence IDs. Findings are AI proposals, never user-adopted. "
                    "Do not invent conflicts, scores, percentages, confidence, or weighting."
                ),
            )
        except AIClientError:
            pass
    return _fallback_proposal(define_output, stress_output)


def _fallback_proposal(define_output: DefineOutput, stress_output: StressTestOutput) -> AlignmentProposal:
    provenance = _ai_provenance("Deterministic proposal from reviewed Define and Stress Test records.")
    functions = [
        FunctionAlignment(
            functionName=moment.name,
            status=(AlignmentFindingStatus.gap if moment.status == "gap-to-close" else AlignmentFindingStatus.aligned),
            reasoning=moment.today or moment.desired_state or "Reviewed against the agreed Moment of Truth.",
            evidenceReferences=moment.evidence_ids,
            provenance=provenance,
        )
        for moment in define_output.agreed_moments
    ]
    gaps: list[AlignmentGap] = []
    actions: list[PriorityAction] = []
    for function, moment in zip(functions, define_output.agreed_moments, strict=True):
        if moment.status != "gap-to-close":
            continue
        gap = AlignmentGap(
            title=f"Gap in {moment.name}",
            description=moment.today or "The agreed Moment of Truth records a gap to close.",
            relatedFunctionId=function.id,
            relatedFrameworkRefs=[f"define.moments.{moment.id}"],
            supportingEvidenceIds=moment.evidence_ids,
            whyItMatters=moment.desired_state or "This gap affects delivery of the agreed purpose framework.",
            suggestedNextAction=moment.the_move,
            provenance=provenance,
        )
        gaps.append(gap)
        if moment.the_move:
            actions.append(
                PriorityAction(
                    title=moment.the_move,
                    action=moment.the_move,
                    rationale=gap.why_it_matters,
                    relatedGapId=gap.id,
                    relatedFunctionId=function.id,
                    evidenceReferences=moment.evidence_ids,
                    order=len(actions),
                    provenance=provenance,
                )
            )
    unresolved = list(define_output.unresolved_questions)
    unresolved.extend(concern for item in stress_output.criteria for concern in item.concerns)
    return AlignmentProposal(
        functionalAlignment=functions,
        gaps=gaps,
        priorityActions=actions,
        unresolvedQuestions=list(dict.fromkeys(unresolved)),
    )


def _validate_proposal(proposal: AlignmentProposal, valid_evidence: list[UUID]) -> None:
    valid = set(valid_evidence)
    referenced = []
    referenced.extend(item for finding in proposal.functional_alignment for item in finding.evidence_references)
    referenced.extend(item for gap in proposal.gaps for item in [*gap.supporting_evidence_ids, *gap.conflicting_evidence_ids])
    referenced.extend(item for action in proposal.priority_actions for item in action.evidence_references)
    if not set(referenced).issubset(valid):
        raise ValueError("Alignment proposal contains evidence outside the canonical handoff.")
    if any(item.adopted or item.status == AlignmentItemStatus.adopted for item in proposal.priority_actions):
        raise ValueError("AI-proposed priority actions cannot be automatically adopted.")


def _link_alignment_items(state: AlignmentState) -> None:
    for function in state.functional_alignment:
        function.gap_ids = [gap.id for gap in state.gaps if gap.related_function_id == function.id]
        function.action_ids = [action.id for action in state.priority_actions if action.related_function_id == function.id]


def _gate(gate_id: str, reference: str, label: str, evidence_ids: list[UUID]) -> ValueGateResult:
    return ValueGateResult(
        gateId=gate_id,
        frameworkReference=reference,
        frameworkLabel=label,
        status=(AlignmentFindingStatus.aligned if evidence_ids else AlignmentFindingStatus.insufficient_evidence),
        reasoning=("Relevant evidence is linked for user review." if evidence_ids else "No supporting evidence is linked; user review is required."),
        supportingEvidenceIds=evidence_ids,
        provenance=_ai_provenance("Deterministic Value Gate against the agreed Define framework."),
    )


def _ai_provenance(rationale: str) -> DefineProvenance:
    return DefineProvenance(
        status=EvidenceStatus.ai_inferred,
        rationale=rationale,
        generatedAt=utc_now(),
        sourceHandoff=ALIGNMENT_HANDOFF,
    )


def _unique_ids(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))
