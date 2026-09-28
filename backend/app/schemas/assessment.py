from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return timezone-aware timestamps for API models."""
    return datetime.now(timezone.utc)


NonEmptyString = Annotated[str, Field(min_length=1)]


class AssessmentStage(StrEnum):
    identify = "identify"
    define = "define"
    stress_test = "stress_test"
    align = "align"
    results = "results"
    measure = "measure"


class AssessmentLifecycleStatus(StrEnum):
    created = "created"
    active = "active"
    stage_completed = "stage_completed"


class AssessmentStageStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class DefineStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    ready_for_review = "ready_for_review"
    completed = "completed"


class DefineApprovalStatus(StrEnum):
    ai_proposed = "ai-proposed"
    user_edited = "user-edited"
    agreed = "agreed"


class ValueChainMomentStatus(StrEnum):
    on_course = "on-course"
    in_progress = "in-progress"
    gap_to_close = "gap-to-close"


class StressTestStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    ready_for_review = "ready_for_review"
    completed = "completed"


class StressTestCriterionStatus(StrEnum):
    supported = "supported"
    needs_review = "needs-review"
    insufficient_evidence = "insufficient-evidence"


class AlignmentStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"


class AlignmentFindingStatus(StrEnum):
    aligned = "aligned"
    tension = "tension"
    gap = "gap"
    insufficient_evidence = "insufficient-evidence"


class AlignmentItemStatus(StrEnum):
    proposed = "proposed"
    adopted = "adopted"
    in_progress = "in-progress"
    completed = "completed"
    dismissed = "dismissed"


class DecisionCanvasStatus(StrEnum):
    draft = "draft"
    reframed = "reframed"
    evaluated = "evaluated"


class PESTLECategory(StrEnum):
    political = "political"
    economic = "economic"
    social = "social"
    technological = "technological"
    legal = "legal"
    environmental = "environmental"


class ResearchSourceType(StrEnum):
    sme_provided = "sme-provided"
    uploaded_evidence = "uploaded-evidence"
    configured_source = "configured-source"
    public_website = "public-website"
    ai_synthesis = "ai-synthesis"


class AIDetectiveClassification(StrEnum):
    correct = "correct"
    wrong = "wrong"
    interesting = "interesting"
    investigate = "investigate"


class SignalHuntDecision(StrEnum):
    unplaced = "unplaced"
    ignore = "ignore"
    watch = "watch"
    opportunity = "opportunity"
    threat = "threat"


class CompanyCardSelectionState(StrEnum):
    current = "current"
    desired = "desired"


class PositioningEvidenceTopic(StrEnum):
    who_served = "who-served"
    value_created = "value-created"
    current_positioning = "current-positioning"
    distinctiveness = "distinctiveness"
    social_contribution = "social-contribution"
    current_vs_desired = "current-vs-desired"


class PerceptionGapResolution(StrEnum):
    unresolved = "unresolved"
    confirmed = "confirmed"
    corrected = "corrected"
    clarified = "clarified"


class StakeholderGroupType(StrEnum):
    customer = "customer"
    employee = "employee"
    supplier = "supplier"
    partner = "partner"
    owner = "owner"
    investor = "investor"
    community = "community"
    regulator = "regulator"
    other = "other"


class StakeholderPosition(StrEnum):
    internal = "internal"
    external = "external"
    both = "both"


class StakeholderLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class IdentifyActivityStatus(StrEnum):
    available = "available"
    ai_running = "ai-running"
    needs_user = "needs-user"
    invite_team = "invite-team"
    completed = "completed"
    locked = "locked"
    conditional = "conditional"
    ready_for_review = "ready-for-review"


class PlaybookCoverageStatus(StrEnum):
    uncovered = "uncovered"
    partial = "partial"
    sufficient = "sufficient"


class EvidenceStatus(StrEnum):
    """Describe whether evidence was confirmed, derived, or inferred by AI."""

    user_confirmed = "user-confirmed"
    source_derived = "source-derived"
    ai_inferred = "ai-inferred"


class IdentifyCompletionStatus(StrEnum):
    in_progress = "in-progress"
    ready_for_review = "ready-for-review"
    completed = "completed"


class OrganisationContext(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    company_name: NonEmptyString | None = Field(default=None, alias="companyName")
    website: AnyUrl | None = None


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    title: NonEmptyString
    source_type: NonEmptyString
    url: AnyUrl | None = None
    captured_at: datetime = Field(default_factory=utc_now)


class IdentifyEvidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    source: EvidenceSource
    claim: NonEmptyString
    summary: NonEmptyString | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_activity: NonEmptyString | None = Field(
        default=None,
        alias="sourceActivity",
    )
    coverage_area_ids: list[NonEmptyString] = Field(
        default_factory=list,
        alias="coverageAreaIds",
    )
    evidence_status: EvidenceStatus = Field(
        default=EvidenceStatus.source_derived,
        alias="evidenceStatus",
    )
    source_reference: NonEmptyString | None = Field(
        default=None,
        alias="sourceReference",
    )
    derived_from_evidence_ids: list[UUID] = Field(
        default_factory=list,
        alias="derivedFromEvidenceIds",
    )


class IdentifyCrossCheck(BaseModel):
    """An explainable conflict found between saved Identify evidence items."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    topic: NonEmptyString
    explanation: NonEmptyString
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    source_activities: list[NonEmptyString] = Field(
        default_factory=list,
        alias="sourceActivities",
    )
    revisit_activity: NonEmptyString | None = Field(
        default=None,
        alias="revisitActivity",
    )
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")


class IdentifyActivityState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    activity_id: NonEmptyString = Field(alias="activityId")
    status: IdentifyActivityStatus
    progress_label: NonEmptyString | None = Field(
        default=None,
        alias="progressLabel",
    )
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class PlaybookCoverage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    area_id: NonEmptyString = Field(alias="areaId")
    label: NonEmptyString
    question: NonEmptyString
    status: PlaybookCoverageStatus = PlaybookCoverageStatus.uncovered
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class ResearchFinding(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    topic: NonEmptyString
    summary: NonEmptyString
    source_type: ResearchSourceType = Field(alias="sourceType")
    source_label: NonEmptyString = Field(alias="sourceLabel")
    source_reference: NonEmptyString | None = Field(
        default=None,
        alias="sourceReference",
    )
    classification: AIDetectiveClassification = (
        AIDetectiveClassification.investigate
    )
    review_note: NonEmptyString | None = Field(default=None, alias="reviewNote")
    collected_at: datetime = Field(default_factory=utc_now, alias="collectedAt")


class ExternalResearchDocument(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: NonEmptyString
    source_type: NonEmptyString = Field(alias="sourceType")
    category: NonEmptyString
    supported_categories: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportedCategories",
    )
    url: AnyUrl
    title: NonEmptyString | None = None
    organisation_domain: NonEmptyString | None = Field(
        default=None,
        alias="organisationDomain",
    )
    retrieved_at: datetime = Field(default_factory=utc_now, alias="retrievedAt")
    status: NonEmptyString
    status_reason: NonEmptyString | None = Field(default=None, alias="statusReason")
    content: NonEmptyString | None = None
    snippet: NonEmptyString | None = None
    content_hash: NonEmptyString | None = Field(default=None, alias="contentHash")


class ExternalResearchCategoryState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    category: NonEmptyString
    status: NonEmptyString
    source_ids: list[NonEmptyString] = Field(default_factory=list, alias="sourceIds")
    message: NonEmptyString | None = None


class ExternalResearchState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    status: NonEmptyString = "idle"
    provider: NonEmptyString = "public-website"
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")
    documents: list[ExternalResearchDocument] = Field(default_factory=list)
    categories: list[ExternalResearchCategoryState] = Field(default_factory=list)
    synthesis_error: NonEmptyString | None = Field(default=None, alias="synthesisError")


class CompanyCardSelection(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    card_id: NonEmptyString = Field(alias="cardId")
    state: CompanyCardSelectionState


class CompanyCardsEvidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    selections: list[CompanyCardSelection] = Field(default_factory=list)
    explanation: NonEmptyString | None = None
    source_activity: NonEmptyString = Field(
        default="company-cards",
        alias="sourceActivity",
    )
    source_label: NonEmptyString = Field(
        default="Company Cards",
        alias="sourceLabel",
    )
    collected_at: datetime = Field(default_factory=utc_now, alias="collectedAt")


class Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    summary: NonEmptyString


class ObservedExperience(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    summary: NonEmptyString
    supporting_evidence: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportingEvidence",
    )


class Gap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    summary: NonEmptyString


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    summary: NonEmptyString


class Touchpoint(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    moment: NonEmptyString
    expectations: list[Expectation] = Field(default_factory=list)
    observed_experiences: list[ObservedExperience] = Field(
        default_factory=list,
        alias="observedExperiences",
    )
    pain_points: list[NonEmptyString] = Field(
        default_factory=list,
        alias="painPoints",
    )
    gaps: list[Gap] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    supporting_evidence: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportingEvidence",
    )


class StakeholderJourney(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    stakeholder_id: UUID = Field(alias="stakeholderId")
    stakeholder_name: NonEmptyString = Field(alias="stakeholderName")
    touchpoints: list[Touchpoint] = Field(default_factory=list)
    supporting_evidence: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportingEvidence",
    )
    source_activity: NonEmptyString = Field(
        default="day-in-their-shoes",
        alias="sourceActivity",
    )
    source_label: NonEmptyString = Field(
        default="A Day in Their Shoes",
        alias="sourceLabel",
    )
    collected_at: datetime = Field(default_factory=utc_now, alias="collectedAt")


class PositioningEvidenceResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    topic: PositioningEvidenceTopic
    prompt: NonEmptyString
    response: NonEmptyString
    supporting_evidence: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportingEvidence",
    )


class WhereDoYouStandEvidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    responses: list[PositioningEvidenceResponse] = Field(default_factory=list)
    source_activity: NonEmptyString = Field(
        default="where-do-you-stand",
        alias="sourceActivity",
    )
    source_label: NonEmptyString = Field(
        default="Where Do You Stand?",
        alias="sourceLabel",
    )
    collected_at: datetime = Field(default_factory=utc_now, alias="collectedAt")


class PerceptionGap(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    topic: NonEmptyString
    perspective_a: NonEmptyString = Field(alias="perspectiveA")
    perspective_b: NonEmptyString = Field(alias="perspectiveB")
    difference: NonEmptyString
    supporting_evidence_ids: list[UUID] = Field(
        default_factory=list,
        alias="supportingEvidenceIds",
    )
    clarification_needed: bool = Field(default=True, alias="clarificationNeeded")
    resolution: PerceptionGapResolution = PerceptionGapResolution.unresolved
    resolution_note: NonEmptyString | None = Field(
        default=None,
        alias="resolutionNote",
    )


class Stakeholder(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    name: NonEmptyString
    group_type: StakeholderGroupType = Field(alias="groupType")
    internal_or_external: StakeholderPosition = Field(alias="internalOrExternal")
    relationship: NonEmptyString | None = None
    importance: StakeholderLevel
    influence: StakeholderLevel
    needs: list[NonEmptyString] = Field(default_factory=list)
    expectations: list[NonEmptyString] = Field(default_factory=list)
    notes: NonEmptyString | None = None
    evidence_source: NonEmptyString = Field(alias="evidenceSource")
    insight: NonEmptyString | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)


class PESTLEEvidenceSource(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID | None = None
    title: NonEmptyString
    source_type: NonEmptyString = Field(alias="sourceType")
    url: AnyUrl | None = None
    summary: NonEmptyString | None = None


class PESTLEFinding(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    category: PESTLECategory
    signal: NonEmptyString
    description: NonEmptyString
    why_it_matters: NonEmptyString = Field(alias="whyItMatters")
    opportunity_or_risk: NonEmptyString = Field(alias="opportunityOrRisk")
    evidence_sources: list[PESTLEEvidenceSource] = Field(
        default_factory=list,
        alias="evidenceSources",
    )
    decision: SignalHuntDecision = SignalHuntDecision.unplaced
    impact: int | None = Field(default=None, ge=0, le=100)
    urgency: int | None = Field(default=None, ge=0, le=100)


class IdentifyTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    name: NonEmptyString
    summary: NonEmptyString
    evidence_ids: list[UUID] = Field(default_factory=list)


class IdentifyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discovery_brief: NonEmptyString | None = None
    research_findings: list[ResearchFinding] = Field(default_factory=list)
    external_research: ExternalResearchState = Field(
        default_factory=ExternalResearchState
    )
    company_cards_evidence: CompanyCardsEvidence | None = None
    stakeholder_journeys: list[StakeholderJourney] = Field(default_factory=list)
    where_do_you_stand_evidence: WhereDoYouStandEvidence | None = None
    perception_gaps: list[PerceptionGap] = Field(default_factory=list)
    cross_check_findings: list[IdentifyCrossCheck] = Field(default_factory=list)
    themes: list[IdentifyTheme] = Field(default_factory=list)
    pestle_findings: list[PESTLEFinding] = Field(default_factory=list)
    stakeholder_insights: list[Stakeholder] = Field(default_factory=list)
    positioning_evidence: list[IdentifyEvidence] = Field(default_factory=list)
    social_contribution_evidence: list[IdentifyEvidence] = Field(default_factory=list)
    vulnerabilities_gaps: list[NonEmptyString] = Field(default_factory=list)
    open_questions: list[NonEmptyString] = Field(default_factory=list)
    evidence_references: list[UUID] = Field(default_factory=list)


class IdentifyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: IdentifyOutput = Field(default_factory=IdentifyOutput)
    evidence: list[IdentifyEvidence] = Field(default_factory=list)
    activity_states: dict[str, IdentifyActivityState] = Field(default_factory=dict)
    playbook_coverage: list[PlaybookCoverage] = Field(default_factory=list)
    completion_status: IdentifyCompletionStatus = IdentifyCompletionStatus.in_progress
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class DefineProvenance(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    status: EvidenceStatus = Field(default=EvidenceStatus.ai_inferred)
    rationale: NonEmptyString | None = None
    generated_at: datetime | None = Field(default=None, alias="generatedAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    source_handoff: NonEmptyString | None = Field(
        default=None,
        alias="sourceHandoff",
    )


class SingleOrganizingIdeaCandidate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    statement: NonEmptyString | None = None
    guiding_star: NonEmptyString | None = Field(default=None, alias="guidingStar")
    meaning: NonEmptyString | None = None
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.ai_proposed,
        alias="approvalStatus",
    )


class PositioningStatement(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    audience: NonEmptyString | None = None
    category_context: NonEmptyString | None = Field(
        default=None,
        alias="categoryContext",
    )
    capability_value: NonEmptyString | None = Field(
        default=None,
        alias="capabilityValue",
    )
    reason_believability: NonEmptyString | None = Field(
        default=None,
        alias="reasonBelievability",
    )
    composed_statement: NonEmptyString | None = Field(
        default=None,
        alias="composedStatement",
    )
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.ai_proposed,
        alias="approvalStatus",
    )


class ValueCommitment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    name: NonEmptyString
    meaning: NonEmptyString | None = None
    supporting_evidence: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportingEvidence",
    )
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.ai_proposed,
        alias="approvalStatus",
    )


class ValueChainMoment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID = Field(default_factory=uuid4)
    name: NonEmptyString
    question: NonEmptyString | None = None
    today: NonEmptyString | None = None
    desired_state: NonEmptyString | None = Field(default=None, alias="desiredState")
    the_move: NonEmptyString | None = Field(default=None, alias="theMove")
    status: ValueChainMomentStatus = ValueChainMomentStatus.in_progress
    supporting_evidence: list[NonEmptyString] = Field(
        default_factory=list,
        alias="supportingEvidence",
    )
    evidence_ids: list[UUID] = Field(default_factory=list, alias="evidenceIds")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    approval_status: DefineApprovalStatus = Field(
        default=DefineApprovalStatus.ai_proposed,
        alias="approvalStatus",
    )


class DefineOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    agreed_soi: SingleOrganizingIdeaCandidate | None = Field(
        default=None,
        alias="agreedSoi",
    )
    agreed_positioning: PositioningStatement | None = Field(
        default=None,
        alias="agreedPositioning",
    )
    agreed_values: list[ValueCommitment] = Field(
        default_factory=list,
        alias="agreedValues",
    )
    agreed_moments: list[ValueChainMoment] = Field(
        default_factory=list,
        alias="agreedMoments",
    )
    unresolved_questions: list[NonEmptyString] = Field(
        default_factory=list,
        alias="unresolvedQuestions",
    )
    evidence_references: list[UUID] = Field(
        default_factory=list,
        alias="evidenceReferences",
    )
    source_handoff: NonEmptyString | None = Field(
        default=None,
        alias="sourceHandoff",
    )
    completion_status: DefineStatus | None = Field(default=None, alias="completionStatus")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class StressTestCriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    criterion_id: NonEmptyString = Field(alias="criterionId")
    name: NonEmptyString
    question: NonEmptyString
    status: StressTestCriterionStatus
    reasoning: NonEmptyString
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, alias="supportingEvidenceIds")
    concerns: list[NonEmptyString] = Field(default_factory=list)
    suggested_refinement: NonEmptyString | None = Field(default=None, alias="suggestedRefinement")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    approval_status: DefineApprovalStatus = Field(default=DefineApprovalStatus.ai_proposed, alias="approvalStatus")


class StressTestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    criteria: list[StressTestCriterionResult] = Field(default_factory=list)
    overarching_question: NonEmptyString = Field(alias="overarchingQuestion")
    overarching_response: NonEmptyString | None = Field(default=None, alias="overarchingResponse")
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    source_handoff: NonEmptyString = Field(default="structured_outputs.define.handoff", alias="sourceHandoff")
    completed_at: datetime | None = Field(default=None, alias="completedAt")


class StressTestState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    assessment_id: UUID | None = Field(default=None, alias="assessmentId")
    status: StressTestStatus = StressTestStatus.not_started
    criteria: list[StressTestCriterionResult] = Field(default_factory=list)
    overarching_question: NonEmptyString = Field(alias="overarchingQuestion")
    overarching_response: NonEmptyString | None = Field(default=None, alias="overarchingResponse")
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    output: StressTestOutput | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class FunctionAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    function_name: NonEmptyString = Field(alias="functionName")
    status: AlignmentFindingStatus
    reasoning: NonEmptyString
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    gap_ids: list[UUID] = Field(default_factory=list, alias="gapIds")
    action_ids: list[UUID] = Field(default_factory=list, alias="actionIds")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class AlignmentGap(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    title: NonEmptyString
    description: NonEmptyString
    related_function_id: UUID | None = Field(default=None, alias="relatedFunctionId")
    related_framework_refs: list[NonEmptyString] = Field(default_factory=list, alias="relatedFrameworkRefs")
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, alias="supportingEvidenceIds")
    conflicting_evidence_ids: list[UUID] = Field(default_factory=list, alias="conflictingEvidenceIds")
    why_it_matters: NonEmptyString = Field(alias="whyItMatters")
    suggested_next_action: NonEmptyString | None = Field(default=None, alias="suggestedNextAction")
    status: AlignmentItemStatus = AlignmentItemStatus.proposed
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class PriorityAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    title: NonEmptyString
    action: NonEmptyString
    rationale: NonEmptyString
    related_gap_id: UUID | None = Field(default=None, alias="relatedGapId")
    related_function_id: UUID | None = Field(default=None, alias="relatedFunctionId")
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    status: AlignmentItemStatus = AlignmentItemStatus.proposed
    adopted: bool = False
    order: int = Field(default=0, ge=0)
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class ValueGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    gate_id: NonEmptyString = Field(alias="gateId")
    framework_reference: NonEmptyString = Field(alias="frameworkReference")
    framework_label: NonEmptyString = Field(alias="frameworkLabel")
    status: AlignmentFindingStatus
    reasoning: NonEmptyString
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, alias="supportingEvidenceIds")
    tensions: list[NonEmptyString] = Field(default_factory=list)
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class SuggestedMove(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    action: NonEmptyString
    rationale: NonEmptyString
    related_gap_id: UUID | None = Field(default=None, alias="relatedGapId")
    related_gate_id: NonEmptyString | None = Field(default=None, alias="relatedGateId")
    related_decision_id: UUID = Field(alias="relatedDecisionId")
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    status: AlignmentItemStatus = AlignmentItemStatus.proposed
    adopted: bool = False
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class AdoptedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    source_move_id: UUID = Field(alias="sourceMoveId")
    decision_id: UUID = Field(alias="decisionId")
    action: NonEmptyString
    rationale: NonEmptyString
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    status: AlignmentItemStatus = AlignmentItemStatus.adopted
    adopted_at: datetime = Field(default_factory=utc_now, alias="adoptedAt")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)


class DecisionCanvas(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    original_question: NonEmptyString = Field(alias="originalQuestion")
    reframed_question: NonEmptyString | None = Field(default=None, alias="reframedQuestion")
    reframe_reasoning: NonEmptyString | None = Field(default=None, alias="reframeReasoning")
    value_gates: list[ValueGateResult] = Field(default_factory=list, alias="valueGates")
    gap_ids: list[UUID] = Field(default_factory=list, alias="gapIds")
    suggested_moves: list[SuggestedMove] = Field(default_factory=list, alias="suggestedMoves")
    adopted_action_ids: list[UUID] = Field(default_factory=list, alias="adoptedActionIds")
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    status: DecisionCanvasStatus = DecisionCanvasStatus.draft
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class ProgressSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: UUID = Field(default_factory=uuid4)
    captured_at: datetime = Field(default_factory=utc_now, alias="capturedAt")
    completed_action_ids: list[UUID] = Field(default_factory=list, alias="completedActionIds")
    outstanding_action_ids: list[UUID] = Field(default_factory=list, alias="outstandingActionIds")
    adopted_action_ids: list[UUID] = Field(default_factory=list, alias="adoptedActionIds")
    resolved_gap_ids: list[UUID] = Field(default_factory=list, alias="resolvedGapIds")
    unresolved_gap_ids: list[UUID] = Field(default_factory=list, alias="unresolvedGapIds")
    observations: list[NonEmptyString] = Field(default_factory=list)
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")


class AlignmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    functional_alignment: list[FunctionAlignment] = Field(default_factory=list, alias="functionalAlignment")
    gaps: list[AlignmentGap] = Field(default_factory=list)
    priority_actions: list[PriorityAction] = Field(default_factory=list, alias="priorityActions")
    decisions: list[DecisionCanvas] = Field(default_factory=list)
    adopted_actions: list[AdoptedAction] = Field(default_factory=list, alias="adoptedActions")
    progress_snapshots: list[ProgressSnapshot] = Field(default_factory=list, alias="progressSnapshots")
    unresolved_questions: list[NonEmptyString] = Field(default_factory=list, alias="unresolvedQuestions")
    evidence_references: list[UUID] = Field(default_factory=list, alias="evidenceReferences")
    source_define_output: NonEmptyString = Field(default="structured_outputs.define", alias="sourceDefineOutput")
    source_stress_test_output: NonEmptyString = Field(default="structured_outputs.stress_test", alias="sourceStressTestOutput")
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class AlignmentState(AlignmentOutput):
    assessment_id: UUID | None = Field(default=None, alias="assessmentId")
    status: AlignmentStatus = AlignmentStatus.not_started
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    output: AlignmentOutput | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")


class DefineState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    assessment_id: UUID | None = Field(default=None, alias="assessmentId")
    status: DefineStatus = DefineStatus.not_started
    source_handoff: NonEmptyString | None = Field(
        default=None,
        alias="sourceHandoff",
    )
    soi_candidate: SingleOrganizingIdeaCandidate | None = Field(
        default=None,
        alias="soiCandidate",
    )
    positioning: PositioningStatement = Field(default_factory=PositioningStatement)
    values: list[ValueCommitment] = Field(default_factory=list)
    moments: list[ValueChainMoment] = Field(default_factory=list)
    unresolved_questions: list[NonEmptyString] = Field(
        default_factory=list,
        alias="unresolvedQuestions",
    )
    evidence_references: list[UUID] = Field(
        default_factory=list,
        alias="evidenceReferences",
    )
    provenance: DefineProvenance = Field(default_factory=DefineProvenance)
    output: DefineOutput | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class AssessmentSessionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    stage: AssessmentStage = AssessmentStage.identify
    organisation: OrganisationContext = Field(default_factory=OrganisationContext)
    company_name: NonEmptyString | None = Field(default=None, alias="companyName")
    website: AnyUrl | None = None


class AssessmentSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    stage: AssessmentStage = AssessmentStage.identify
    next_stage: AssessmentStage | None = None
    lifecycle_status: AssessmentLifecycleStatus = AssessmentLifecycleStatus.active
    stage_statuses: dict[AssessmentStage, AssessmentStageStatus] = Field(
        default_factory=lambda: {
            AssessmentStage.identify: AssessmentStageStatus.in_progress
        }
    )
    stage_states: dict[AssessmentStage, dict[str, Any]] = Field(default_factory=dict)
    structured_outputs: dict[AssessmentStage, dict[str, Any]] = Field(
        default_factory=dict
    )
    handoffs: list[dict[str, Any]] = Field(default_factory=list)
    revisit_routes: list[dict[str, Any]] = Field(default_factory=list)
    organisation: OrganisationContext = Field(default_factory=OrganisationContext)
    identify: IdentifyState = Field(default_factory=IdentifyState)
    define: DefineState = Field(default_factory=DefineState)
    stress_test: StressTestState = Field(
        default_factory=lambda: StressTestState(
            overarchingQuestion=(
                "Will this SOI® help the organisation thrive while making a "
                "positive contribution to society?"
            )
        )
    )
    alignment: AlignmentState = Field(default_factory=AlignmentState)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
