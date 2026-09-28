import re
from datetime import datetime
from itertools import combinations
from uuid import UUID, NAMESPACE_URL, uuid5

from app.config.identify_dependencies import (
    DAY_IN_THEIR_SHOES_DEPENDENCY,
    PERCEPTION_GAPS_DEPENDENCY,
)
from app.schemas.assessment import (
    AssessmentSession,
    EvidenceSource,
    EvidenceStatus,
    IdentifyActivityState,
    IdentifyActivityStatus,
    IdentifyEvidence,
    IdentifyCrossCheck,
    IdentifyState,
    PlaybookCoverage,
    PlaybookCoverageStatus,
    utc_now,
)
from app.schemas.conversation import QuestionEvidenceArea
from app.stages.identify import identify_stage_config


IDENTIFY_ACTIVITY_IDS = [
    "ai-detective",
    "signal-hunt",
    "discover-synthesis",
    "who-matters",
    "hot-seat",
    "company-cards",
    "listen-summary",
    "day-in-their-shoes",
    "where-do-you-stand",
    "perception-gaps",
    "evidence-wall",
    "identify-brief",
]


def initialize_identify_foundation(session: AssessmentSession) -> None:
    session.identify.activity_states = _activity_states(session.identify)
    session.identify.playbook_coverage = _playbook_coverage(session.identify)


def refresh_identify_foundation(session: AssessmentSession) -> None:
    session.identify.output.cross_check_findings = cross_check_identify_evidence(
        session.identify
    )
    session.identify.activity_states = _activity_states(session.identify)
    session.identify.playbook_coverage = _playbook_coverage(session.identify)


def replace_activity_evidence(
    state: IdentifyState,
    activity_id: str,
    evidence: list[IdentifyEvidence],
) -> None:
    state.evidence = [
        item for item in state.evidence if item.source_activity != activity_id
    ]
    state.evidence.extend(evidence)
    state.output.evidence_references = [item.id for item in state.evidence]


def evidence_from_research_findings(state: IdentifyState) -> list[IdentifyEvidence]:
    evidence: list[IdentifyEvidence] = []
    for finding in state.output.research_findings:
        coverage_ids = coverage_area_ids_for_text(
            f"{finding.topic} {finding.summary} {finding.source_label}"
        )
        if finding.classification == "wrong":
            coverage_ids.append("vulnerabilities")
        evidence.append(
            _evidence(
                activity_id="ai-detective",
                source_title=finding.source_label,
                claim=finding.summary,
                summary=f"{finding.topic} ({finding.classification.value})",
                coverage_area_ids=_unique(coverage_ids),
                evidence_status=(
                    EvidenceStatus.ai_inferred
                    if finding.source_type == "ai-synthesis"
                    else EvidenceStatus.user_confirmed
                    if finding.source_type == "sme-provided"
                    else EvidenceStatus.source_derived
                ),
                source_reference=(
                    finding.source_reference or f"research-finding:{finding.id}"
                ),
                source_type=finding.source_type.value,
                captured_at=finding.collected_at,
            )
        )
    return evidence


def evidence_from_signal_hunt(state: IdentifyState) -> list[IdentifyEvidence]:
    evidence: list[IdentifyEvidence] = []
    for finding in state.output.pestle_findings:
        if finding.decision in {"unplaced", "ignore"}:
            continue
        area_id = f"{finding.category.value}_context"
        coverage_ids = [
            area_id,
            *coverage_area_ids_for_text(
                f"{finding.signal} {finding.description} "
                f"{finding.why_it_matters} {finding.opportunity_or_risk}"
            ),
        ]
        if finding.decision in {"opportunity", "threat"}:
            coverage_ids.append("vulnerabilities")
        evidence.append(
            _evidence(
                activity_id="signal-hunt",
                source_title="Signal Hunt",
                claim=finding.description,
                summary=finding.signal,
                coverage_area_ids=_unique(coverage_ids),
                source_reference=f"signal-hunt:{finding.id}",
            )
        )
    return evidence


def evidence_from_stakeholders(state: IdentifyState) -> list[IdentifyEvidence]:
    evidence: list[IdentifyEvidence] = []
    for stakeholder in state.output.stakeholder_insights:
        text = " ".join(
            [
                stakeholder.name,
                stakeholder.group_type.value,
                stakeholder.relationship or "",
                " ".join(stakeholder.needs),
                " ".join(stakeholder.expectations),
                stakeholder.notes or "",
                stakeholder.insight or "",
            ]
        )
        coverage_ids = coverage_area_ids_for_text(text)
        if stakeholder.group_type.value == "customer":
            coverage_ids.append("customer_needs")
        if stakeholder.group_type.value == "employee":
            coverage_ids.append("employee_experience")
        if stakeholder.group_type.value in {"supplier", "partner", "investor"}:
            coverage_ids.append("partner_supplier_context")
        evidence.append(
            _evidence(
                activity_id="who-matters",
                source_title="Who Matters?",
                claim=stakeholder.insight or text,
                summary=stakeholder.name,
                coverage_area_ids=_unique(coverage_ids),
                evidence_status=EvidenceStatus.user_confirmed,
                source_reference=f"stakeholder:{stakeholder.id}",
            )
        )
    return evidence


def evidence_from_company_cards(state: IdentifyState) -> list[IdentifyEvidence]:
    card_evidence = state.output.company_cards_evidence
    if card_evidence is None:
        return []
    selected = ", ".join(
        f"{selection.card_id}:{selection.state.value}"
        for selection in card_evidence.selections
    )
    claim = (
        card_evidence.explanation
        or f"Selected company identity cards: {selected}"
    )
    return [
        _evidence(
            activity_id="company-cards",
            source_title="Company Cards",
            claim=claim,
            summary="Today and future identity selections",
            coverage_area_ids=_unique(
                [
                    "best_work",
                    "market_position",
                    "purpose_driven_proof",
                    *coverage_area_ids_for_text(claim),
                ]
            ),
            evidence_status=EvidenceStatus.user_confirmed,
            source_reference=f"company-cards:{card_evidence.id}",
            captured_at=card_evidence.collected_at,
        )
    ]


def evidence_from_stakeholder_journeys(
    state: IdentifyState,
) -> list[IdentifyEvidence]:
    evidence: list[IdentifyEvidence] = []
    for journey in state.output.stakeholder_journeys:
        for touchpoint in journey.touchpoints:
            text = " ".join(
                [
                    journey.stakeholder_name,
                    touchpoint.moment,
                    " ".join(item.summary for item in touchpoint.expectations),
                    " ".join(
                        item.summary for item in touchpoint.observed_experiences
                    ),
                    " ".join(touchpoint.pain_points),
                    " ".join(item.summary for item in touchpoint.gaps),
                    " ".join(item.summary for item in touchpoint.opportunities),
                    " ".join(touchpoint.supporting_evidence),
                ]
            )
            evidence.append(
                _evidence(
                    activity_id="day-in-their-shoes",
                    source_title="A Day in Their Shoes",
                    claim=text,
                    summary=touchpoint.moment,
                    coverage_area_ids=_unique(
                        [
                            "customer_needs",
                            "employee_experience",
                            "vulnerabilities",
                            *coverage_area_ids_for_text(text),
                        ]
                    ),
                    evidence_status=EvidenceStatus.user_confirmed,
                    source_reference=f"stakeholder-journey:{journey.id}",
                    captured_at=journey.collected_at,
                )
            )
    return evidence


def evidence_from_where_do_you_stand(state: IdentifyState) -> list[IdentifyEvidence]:
    standing = state.output.where_do_you_stand_evidence
    if standing is None:
        return []
    evidence: list[IdentifyEvidence] = []
    for response in standing.responses:
        coverage_ids = coverage_area_ids_for_text(
            f"{response.prompt} {response.response}"
        )
        if response.topic.value == "social-contribution":
            coverage_ids.append("social_contribution")
        elif response.topic.value == "who-served":
            coverage_ids.append("organisation_basics")
        elif response.topic.value == "current-vs-desired":
            coverage_ids.append("vulnerabilities")
        else:
            coverage_ids.append("market_position")
        evidence.append(
            _evidence(
                activity_id="where-do-you-stand",
                source_title="Where Do You Stand?",
                claim=response.response,
                summary=response.prompt,
                coverage_area_ids=_unique(coverage_ids),
                evidence_status=EvidenceStatus.user_confirmed,
                source_reference=f"positioning-response:{response.id}",
                captured_at=standing.collected_at,
            )
        )
    return evidence


def evidence_from_perception_gaps(state: IdentifyState) -> list[IdentifyEvidence]:
    return [
        _evidence(
            activity_id="perception-gaps",
            source_title="Perception Gaps",
            claim=gap.difference,
            summary=gap.topic,
            coverage_area_ids=_unique(
                ["vulnerabilities", *coverage_area_ids_for_text(gap.difference)]
            ),
            evidence_status=EvidenceStatus.user_confirmed,
            source_reference=f"perception-gap:{gap.id}",
            derived_from_evidence_ids=gap.supporting_evidence_ids,
        )
        for gap in state.output.perception_gaps
    ]


def evidence_from_discover_synthesis(state: IdentifyState) -> list[IdentifyEvidence]:
    if not state.output.discovery_brief:
        return []
    return [
        _evidence(
            activity_id="discover-synthesis",
            source_title="Discover Synthesis",
            claim=state.output.discovery_brief,
            summary="Discover synthesis statement",
            coverage_area_ids=_unique(
                [
                    "organisation_basics",
                    "market_position",
                    *coverage_area_ids_for_text(state.output.discovery_brief),
                ]
            ),
        )
    ]


def coverage_area_ids_for_text(text: str) -> list[str]:
    lowered = text.lower()
    area_ids: list[str] = []
    for area in identify_stage_config.question_evidence_areas:
        if any(keyword in lowered for keyword in area.keywords):
            area_ids.append(area.id)
    return _unique(area_ids)


CONTRADICTION_CUES = (
    (("fast", "speed", "quick", "efficient"), ("slow", "delay", "late", "waiting")),
    (("simple", "clear", "easy"), ("complex", "confusing", "friction", "painful")),
    (("personal", "warm", "listening"), ("impersonal", "distant", "ignored")),
    (("trusted", "reliable", "consistent"), ("distrust", "unreliable", "inconsistent")),
    (("premium", "quality"), ("lowest-cost", "cheap", "budget")),
)


def claims_are_contradictory(first: str, second: str) -> bool:
    """Return true only for explicit opposing claims, not mere differences."""
    first_text = first.lower()
    second_text = second.lower()
    for positive, negative in CONTRADICTION_CUES:
        if (_has_any(first_text, positive) and _has_any(second_text, negative)) or (
            _has_any(first_text, negative) and _has_any(second_text, positive)
        ):
            return True
    return False


def cross_check_identify_evidence(state: IdentifyState) -> list[IdentifyCrossCheck]:
    """Compare evidence across activities where structured coverage overlaps."""
    findings: list[IdentifyCrossCheck] = []
    for first, second in combinations(state.evidence, 2):
        if not first.source_activity or first.source_activity == second.source_activity:
            continue
        shared_areas = sorted(
            set(first.coverage_area_ids) & set(second.coverage_area_ids)
        )
        if not shared_areas or not claims_are_contradictory(first.claim, second.claim):
            continue
        evidence_ids = sorted((str(first.id), str(second.id)))
        topic = shared_areas[0]
        findings.append(
            IdentifyCrossCheck(
                id=uuid5(
                    NAMESPACE_URL,
                    f"purpos-cross-check:{topic}:{':'.join(evidence_ids)}",
                ),
                topic=topic,
                explanation=(
                    f"{first.source.title} and {second.source.title} provide "
                    f"opposing evidence about {topic.replace('_', ' ')}."
                ),
                evidenceIds=[first.id, second.id],
                sourceActivities=[first.source_activity, second.source_activity],
                revisitActivity=second.source_activity,
            )
        )
    return findings


def _activity_states(state: IdentifyState) -> dict[str, IdentifyActivityState]:
    statuses = {
        "ai-detective": (
            IdentifyActivityStatus.completed
            if state.output.research_findings
            else IdentifyActivityStatus.available
        ),
        "signal-hunt": (
            IdentifyActivityStatus.completed
            if _has_reviewed_all_signals(state)
            else IdentifyActivityStatus.needs_user
            if _has_any_signal_decisions(state)
            else IdentifyActivityStatus.conditional
        ),
        "discover-synthesis": (
            IdentifyActivityStatus.completed
            if state.output.discovery_brief
            else (
                IdentifyActivityStatus.available
                if state.output.research_findings or _has_any_signal_decisions(state)
                else IdentifyActivityStatus.locked
            )
        ),
        "who-matters": (
            IdentifyActivityStatus.completed
            if state.output.stakeholder_insights
            else IdentifyActivityStatus.available
        ),
        "hot-seat": (
            IdentifyActivityStatus.completed
            if any(
                item.source_activity == "hot-seat"
                for item in state.evidence
            )
            else IdentifyActivityStatus.invite_team
        ),
        "company-cards": (
            IdentifyActivityStatus.completed
            if state.output.company_cards_evidence is not None
            else IdentifyActivityStatus.needs_user
        ),
        "listen-summary": (
            IdentifyActivityStatus.completed
            if _listen_evidence_count(state) >= 3
            else IdentifyActivityStatus.available
            if _listen_evidence_count(state) > 0
            else IdentifyActivityStatus.locked
        ),
        "day-in-their-shoes": (
            IdentifyActivityStatus.completed
            if state.output.stakeholder_journeys
            else (
                IdentifyActivityStatus.available
                if DAY_IN_THEIR_SHOES_DEPENDENCY.is_satisfied(state)
                else IdentifyActivityStatus.locked
            )
        ),
        "where-do-you-stand": (
            IdentifyActivityStatus.completed
            if state.output.where_do_you_stand_evidence is not None
            else IdentifyActivityStatus.available
        ),
        "perception-gaps": (
            IdentifyActivityStatus.completed
            if state.output.perception_gaps
            else (
                IdentifyActivityStatus.conditional
                if PERCEPTION_GAPS_DEPENDENCY.is_satisfied(state)
                else IdentifyActivityStatus.locked
            )
        ),
        "evidence-wall": (
            IdentifyActivityStatus.completed
            if state.output.themes
            else IdentifyActivityStatus.available
            if state.evidence
            else IdentifyActivityStatus.locked
        ),
        "identify-brief": (
            IdentifyActivityStatus.completed
            if state.completion_status == "completed"
            else IdentifyActivityStatus.ready_for_review
            if _identify_handoff_ready(state)
            else IdentifyActivityStatus.available
            if state.output.themes
            else IdentifyActivityStatus.locked
        ),
    }
    return {
        activity_id: IdentifyActivityState(
            activityId=activity_id,
            status=status,
            progressLabel=_activity_progress_label(state, activity_id),
        )
        for activity_id, status in statuses.items()
    }


def _playbook_coverage(state: IdentifyState) -> list[PlaybookCoverage]:
    evidence_by_area: dict[str, list[UUID]] = {
        area.id: [] for area in identify_stage_config.question_evidence_areas
    }
    for item in state.evidence:
        for area_id in item.coverage_area_ids:
            if area_id in evidence_by_area:
                evidence_by_area[area_id].append(item.id)

    return [
        PlaybookCoverage(
            areaId=area.id,
            label=area.label,
            question=area.question,
            status=_coverage_status(area, evidence_by_area[area.id]),
            evidenceIds=evidence_by_area[area.id],
        )
        for area in identify_stage_config.question_evidence_areas
    ]


def _coverage_status(
    area: QuestionEvidenceArea,
    evidence_ids: list[UUID],
) -> PlaybookCoverageStatus:
    count = len(evidence_ids)
    if count == 0:
        return PlaybookCoverageStatus.uncovered
    if count >= 2 or area.structured_field in {
        "evidence_references",
        "open_questions",
        "vulnerabilities_gaps",
    }:
        return PlaybookCoverageStatus.sufficient
    return PlaybookCoverageStatus.partial


def _sufficient_coverage_count(state: IdentifyState) -> int:
    return sum(
        1
        for item in _playbook_coverage(state)
        if item.status == PlaybookCoverageStatus.sufficient
    )


def _has_any_signal_decisions(state: IdentifyState) -> bool:
    return bool(state.output.pestle_findings) and any(
        finding.decision != "unplaced"
        for finding in state.output.pestle_findings
    )


def _has_reviewed_all_signals(state: IdentifyState) -> bool:
    return bool(state.output.pestle_findings) and all(
        finding.decision != "unplaced"
        for finding in state.output.pestle_findings
    )


def _activity_progress_label(state: IdentifyState, activity_id: str) -> str:
    if activity_id == "ai-detective":
        return f"{len(state.output.research_findings)} findings"
    if activity_id == "signal-hunt":
        placed = len(
            [
                finding
                for finding in state.output.pestle_findings
                if finding.decision != "unplaced"
            ]
        )
        return f"{placed}/{len(state.output.pestle_findings)} signals placed"
    if activity_id == "discover-synthesis":
        return "Ready" if state.output.discovery_brief else "Needs Discover evidence"
    if activity_id == "who-matters":
        return f"{len(state.output.stakeholder_insights)} stakeholders"
    if activity_id == "hot-seat":
        evidence_count = len(
            [
                item
                for item in state.evidence
                if item.source_activity == "hot-seat"
            ]
        )
        return f"{evidence_count} evidence updates"
    if activity_id == "company-cards":
        evidence = state.output.company_cards_evidence
        if evidence is None:
            return "0 selections"
        return f"{len(evidence.selections)} selections"
    if activity_id == "listen-summary":
        return f"{_listen_evidence_count(state)} Listen evidence items"
    if activity_id == "day-in-their-shoes":
        return f"{len(state.output.stakeholder_journeys)} journeys"
    if activity_id == "where-do-you-stand":
        evidence = state.output.where_do_you_stand_evidence
        if evidence is None:
            return "0 responses"
        return f"{len(evidence.responses)} responses"
    if activity_id == "perception-gaps":
        return f"{len(state.output.perception_gaps)} gaps"
    if activity_id == "evidence-wall":
        if state.output.themes:
            return f"{len(state.output.themes)} themes saved"
        return f"{len(state.evidence)} evidence items"
    if activity_id == "identify-brief":
        covered = len(
            [
                item
                for item in _playbook_coverage(state)
                if item.status in {
                    PlaybookCoverageStatus.partial,
                    PlaybookCoverageStatus.sufficient,
                }
            ]
        )
        return f"{covered}/{len(state.playbook_coverage) or 20} areas covered"
    return f"{len(state.evidence)} evidence items"


def _listen_evidence_count(state: IdentifyState) -> int:
    return len(
        [
            item
            for item in state.evidence
            if item.source_activity in {"who-matters", "hot-seat", "company-cards"}
        ]
    )


def _identify_handoff_ready(state: IdentifyState) -> bool:
    source_activities = {
        item.source_activity
        for item in state.evidence
        if item.source_activity is not None
    }
    has_discover = bool(
        source_activities
        & {"ai-detective", "signal-hunt", "discover-synthesis"}
    )
    has_listen = bool(
        source_activities
        & {"who-matters", "hot-seat", "company-cards", "listen-summary"}
    )
    has_understand = bool(
        source_activities
        & {
            "day-in-their-shoes",
            "where-do-you-stand",
            "perception-gaps",
        }
    )
    covered_area_count = len(
        [
            area
            for area in _playbook_coverage(state)
            if area.status in {
                PlaybookCoverageStatus.partial,
                PlaybookCoverageStatus.sufficient,
            }
        ]
    )
    resolved_cross_checks = {
        frozenset(gap.supporting_evidence_ids)
        for gap in state.output.perception_gaps
        if not gap.clarification_needed and gap.resolution != "unresolved"
    }
    has_unresolved_cross_check = any(
        frozenset(finding.evidence_ids) not in resolved_cross_checks
        for finding in state.output.cross_check_findings
    )
    return (
        has_discover
        and has_listen
        and has_understand
        and bool(state.output.themes)
        and covered_area_count > 0
        and not has_unresolved_cross_check
    )


def _evidence(
    activity_id: str,
    source_title: str,
    claim: str,
    summary: str | None,
    coverage_area_ids: list[str],
    evidence_status: EvidenceStatus = EvidenceStatus.source_derived,
    source_reference: str | None = None,
    derived_from_evidence_ids: list[UUID] | None = None,
    source_type: str = "identify-activity",
    captured_at: datetime | None = None,
) -> IdentifyEvidence:
    return IdentifyEvidence(
        source=EvidenceSource(
            title=source_title,
            source_type=source_type,
            **({"captured_at": captured_at} if captured_at is not None else {}),
        ),
        claim=claim,
        summary=summary,
        sourceActivity=activity_id,
        coverageAreaIds=coverage_area_ids,
        evidenceStatus=evidence_status,
        sourceReference=source_reference,
        derivedFromEvidenceIds=derived_from_evidence_ids or [],
    )


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(cue)}(?!\w)", text) is not None
        for cue in cues
    )


def _unique(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return unique_values
