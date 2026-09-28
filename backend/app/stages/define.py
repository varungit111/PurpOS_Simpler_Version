from app.schemas.assessment import AssessmentStage
from app.schemas.conversation import (
    CompletionCriterion,
    CrossCheckTarget,
    QuestionEvidenceArea,
    StageConfig,
)


define_stage_config = StageConfig(
    stage=AssessmentStage.define,
    system_instructions=(
        "Use the completed Identify handoff to propose editable Define outputs: "
        "Single Organizing Idea, Positioning Statement, Values/commitments, "
        "and Value Chain/Moments of Truth. Keep all proposals evidence-linked "
        "and leave final agreement to the user."
    ),
    question_requirements=[
        "Start only from the canonical persisted Identify handoff.",
        "Ask for refinement when proposed SOI, positioning, values, or moments lack evidence.",
        "Treat generated content as a proposal until the user edits or agrees it.",
    ],
    evidence_requirements=[
        "Reference Identify evidence IDs where available.",
        "Surface unresolved questions without blocking Define initialization.",
        "Do not invent source references or numerical scores.",
    ],
    required_structured_fields=[
        "soi_candidate",
        "positioning",
        "values",
        "moments",
        "unresolved_questions",
        "evidence_references",
    ],
    available_tools=["shared_ai_client"],
    output_schema="DefineOutput",
    completion_criteria=[
        CompletionCriterion(
            name="future_define_completion",
            description=(
                "Define completion and SOI Stress Test readiness are handled by "
                "later tasks; this foundation only initializes and edits Define."
            ),
        )
    ],
    cross_check_targets=[
        CrossCheckTarget(
            name="single_organizing_idea",
            description="Proposed SOI and guiding-star language.",
            fields=["soi_candidate"],
            keywords=["soi", "single", "organizing", "organising", "guiding star"],
        ),
        CrossCheckTarget(
            name="positioning_statement",
            description="Positioning statement scaffold and composed statement.",
            fields=["positioning"],
            keywords=["position", "audience", "category", "because"],
        ),
        CrossCheckTarget(
            name="values_commitments",
            description="Values and commitments proposed from Identify evidence.",
            fields=["values"],
            keywords=["value", "commitment", "principle"],
        ),
        CrossCheckTarget(
            name="moments_of_truth",
            description="Value-chain moments, current state, desired state and moves.",
            fields=["moments"],
            keywords=["moment", "today", "standard", "move", "gap"],
        ),
    ],
    question_evidence_areas=[
        QuestionEvidenceArea(
            id="soi_candidate",
            label="Single Organizing Idea",
            question="What should the proposed Single Organizing Idea become?",
            evidence_prompt="Link the guiding-star idea to Identify evidence.",
            structured_field="soi_candidate",
            keywords=["soi", "idea", "guiding", "purpose"],
        ),
        QuestionEvidenceArea(
            id="positioning",
            label="Positioning Statement",
            question="Which part of the positioning statement needs refinement?",
            evidence_prompt="Use audience, category, value and believability evidence.",
            structured_field="positioning",
            keywords=["positioning", "audience", "category", "value", "because"],
        ),
        QuestionEvidenceArea(
            id="values",
            label="Values / commitments",
            question="Which values or commitments feel right, missing, or unsupported?",
            evidence_prompt="Connect each commitment to Identify evidence.",
            structured_field="values",
            keywords=["values", "commitments", "meaning"],
        ),
        QuestionEvidenceArea(
            id="moments",
            label="Value Chain / Moments of Truth",
            question="Which moments of truth need a clearer Today, desired state, or Move?",
            evidence_prompt="Use stakeholder and journey evidence where available.",
            structured_field="moments",
            keywords=["value chain", "moments", "today", "standard", "move"],
        ),
    ],
    questions=[
        "Does this proposed Single Organizing Idea feel true to the evidence?",
        "Which positioning statement slot needs SME refinement?",
        "Which values or commitments should be edited before they are agreed?",
        "Where in the value chain is there a gap to close?",
    ],
)
