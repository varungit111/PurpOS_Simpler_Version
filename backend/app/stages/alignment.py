from app.schemas.assessment import AssessmentStage
from app.schemas.conversation import StageConfig


alignment_stage_config = StageConfig(
    stage=AssessmentStage.align,
    system_instructions=(
        "Support evidence-linked qualitative Alignment work from the completed "
        "Define and Stress Test handoff. Never invent scores, weighting, or adoption."
    ),
    evidence_requirements=[
        "Reference only evidence IDs present in the canonical cross-stage handoff."
    ],
    required_structured_fields=[
        "functional_alignment",
        "gaps",
        "priority_actions",
        "evidence_references",
    ],
    available_tools=["shared_ai_client"],
    output_schema="AlignmentOutput",
)
