from app.schemas.assessment import AssessmentStage
from app.schemas.conversation import StageConfig
from app.stages.define import define_stage_config
from app.stages.identify import identify_stage_config
from app.stages.stress_test import stress_test_stage_config
from app.stages.alignment import alignment_stage_config


stage_configs: dict[AssessmentStage, StageConfig] = {
    AssessmentStage.identify: identify_stage_config,
    AssessmentStage.define: define_stage_config,
    AssessmentStage.stress_test: stress_test_stage_config,
    AssessmentStage.align: alignment_stage_config,
}


stage_order: tuple[AssessmentStage, ...] = (
    AssessmentStage.identify,
    AssessmentStage.define,
    AssessmentStage.stress_test,
    AssessmentStage.align,
    AssessmentStage.results,
    AssessmentStage.measure,
)


def get_stage_config(stage: AssessmentStage) -> StageConfig | None:
    config = stage_configs.get(stage)
    if config is None:
        return None
    return config.model_copy(deep=True)


def get_next_stage(stage: AssessmentStage) -> AssessmentStage | None:
    try:
        index = stage_order.index(stage)
    except ValueError:
        return None

    next_index = index + 1
    if next_index >= len(stage_order):
        return None
    return stage_order[next_index]
