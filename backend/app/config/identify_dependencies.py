from dataclasses import dataclass

from app.schemas.assessment import IdentifyState


@dataclass(frozen=True)
class ActivityDependencyRule:
    activity_id: str
    required_activity_id: str
    locked_message: str
    minimum_sources: int | None = None

    def is_satisfied(self, state: IdentifyState) -> bool:
        if self.required_activity_id == "who-matters":
            return len(state.output.stakeholder_insights) > 0
        if self.required_activity_id == "meaningful-identify-evidence":
            return count_meaningful_identify_evidence_sources(state) >= (
                self.minimum_sources or 1
            )
        return False


DAY_IN_THEIR_SHOES_DEPENDENCY = ActivityDependencyRule(
    activity_id="day-in-their-shoes",
    required_activity_id="who-matters",
    locked_message=(
        "Add at least one stakeholder in Who Matters? before mapping journeys."
    ),
)

PERCEPTION_GAPS_DEPENDENCY = ActivityDependencyRule(
    activity_id="perception-gaps",
    required_activity_id="meaningful-identify-evidence",
    minimum_sources=2,
    locked_message=(
        "Perception Gaps needs at least two meaningful Identify evidence "
        "sources before differences can be reviewed."
    ),
)


def count_meaningful_identify_evidence_sources(state: IdentifyState) -> int:
    sources = [
        bool(state.output.research_findings),
        bool(state.output.stakeholder_insights),
        state.output.company_cards_evidence is not None,
        bool(state.output.stakeholder_journeys),
        bool(state.evidence),
        bool(state.output.where_do_you_stand_evidence),
        bool(state.output.pestle_findings),
        bool(state.output.positioning_evidence),
        bool(state.output.social_contribution_evidence),
    ]
    return sum(1 for source_exists in sources if source_exists)
