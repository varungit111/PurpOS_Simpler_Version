from dataclasses import dataclass
from uuid import UUID

from app.schemas.assessment import AssessmentSession
from app.services.identify_completion import get_persisted_identify_handoff


@dataclass(frozen=True)
class DefineEvidenceRecord:
    id: UUID
    kind: str
    title: str
    text: str
    summary: str | None = None
    source_activity: str | None = None
    coverage_area_ids: tuple[str, ...] = ()

    def prompt_payload(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "kind": self.kind,
            "title": self.title,
            "text": self.text,
            "summary": self.summary,
        }


def get_define_evidence_ids(session: AssessmentSession) -> set[UUID]:
    """Return persisted evidence IDs that Define is allowed to reference."""
    evidence_ids = {item.id for item in session.identify.evidence}
    handoff = get_persisted_identify_handoff(session)
    if handoff is None:
        return evidence_ids

    evidence_ids.update(handoff.evidence_references)
    evidence_ids.update(handoff.strongest_evidence_ids)
    evidence_ids.update(item.id for item in handoff.output.positioning_evidence)
    evidence_ids.update(
        item.id for item in handoff.output.social_contribution_evidence
    )
    evidence_ids.update(item.id for item in handoff.output.research_findings)
    if handoff.output.company_cards_evidence is not None:
        evidence_ids.add(handoff.output.company_cards_evidence.id)
    return evidence_ids


def get_define_evidence_records(
    session: AssessmentSession,
) -> dict[UUID, DefineEvidenceRecord]:
    """Resolve canonical Define evidence IDs to their persisted content."""
    records: dict[UUID, DefineEvidenceRecord] = {}
    handoff = get_persisted_identify_handoff(session)

    identify_items = list(session.identify.evidence)
    if handoff is not None:
        identify_items.extend(handoff.output.positioning_evidence)
        identify_items.extend(handoff.output.social_contribution_evidence)
    for item in identify_items:
        records[item.id] = DefineEvidenceRecord(
            id=item.id,
            kind="identify-evidence",
            title=item.source.title,
            text=item.claim,
            summary=item.summary,
            source_activity=item.source_activity,
            coverage_area_ids=tuple(item.coverage_area_ids),
        )

    if handoff is None:
        return records

    for item in handoff.output.research_findings:
        records[item.id] = DefineEvidenceRecord(
            id=item.id,
            kind="research-finding",
            title=item.topic,
            text=item.summary,
            summary=item.source_label,
            source_activity="ai-detective",
        )

    company_cards = handoff.output.company_cards_evidence
    if company_cards is not None:
        current = [
            item.card_id
            for item in company_cards.selections
            if item.state == "current"
        ]
        desired = [
            item.card_id
            for item in company_cards.selections
            if item.state == "desired"
        ]
        details = []
        if company_cards.explanation:
            details.append(company_cards.explanation)
        if current:
            details.append(f"Current identity selections: {', '.join(current)}.")
        if desired:
            details.append(f"Desired identity selections: {', '.join(desired)}.")
        records[company_cards.id] = DefineEvidenceRecord(
            id=company_cards.id,
            kind="company-cards-evidence",
            title=company_cards.source_label,
            text=" ".join(details) or "Company identity selections were recorded.",
            summary=company_cards.explanation,
            source_activity=company_cards.source_activity,
            coverage_area_ids=(
                "organisation_basics",
                "market_position",
                "purpose_driven_proof",
            ),
        )
    return records
