from app.schemas.assessment import AssessmentStage
from app.schemas.conversation import StageConfig


stress_test_stage_config = StageConfig(
    stage=AssessmentStage.stress_test,
    system_instructions="Apply the fixed CORE Playbook eight-point SOI Stress Test to the agreed Define handoff. Never add criteria or scores.",
    evidence_requirements=["Preserve evidence IDs and state insufficiency honestly."],
    required_structured_fields=["criteria", "overarching_question", "evidence_references"],
    available_tools=["shared_ai_client"],
    output_schema="StressTestOutput",
)
