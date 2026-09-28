from collections.abc import Collection
from typing import Any

from app.schemas.assessment import EvidenceStatus, IdentifyEvidence, IdentifyState


DEFAULT_MAX_EVIDENCE_ITEMS = 24
MAX_ITEMS_PER_ACTIVITY = 4
MAX_CLAIM_CHARS = 320
MAX_SUMMARY_CHARS = 160
MAX_SOURCE_CHARS = 120
MAX_REFERENCE_CHARS = 180


def build_identify_evidence_context(
    state: IdentifyState,
    *,
    source_activities: Collection[str] | None = None,
    preferred_area_ids: Collection[str] = (),
    max_items: int = DEFAULT_MAX_EVIDENCE_ITEMS,
) -> list[dict[str, Any]]:
    """Return bounded, provenance-aware Identify evidence without raw documents."""
    allowed_activities = set(source_activities or ())
    preferred_areas = set(preferred_area_ids)
    retrieved_documents = {
        document.id: document
        for document in state.output.external_research.documents
        if document.status == "retrieved"
    }

    eligible: list[tuple[int, int, int, str, IdentifyEvidence]] = []
    for item in state.evidence:
        activity = item.source_activity
        if allowed_activities and activity not in allowed_activities:
            continue

        document = None
        if item.source.source_type == "public-website":
            if item.source_reference is None:
                continue
            document = retrieved_documents.get(item.source_reference)
            if document is None:
                continue

        relevance_rank = (
            0
            if preferred_areas.intersection(item.coverage_area_ids)
            else 1
        )
        status_rank = {
            EvidenceStatus.source_derived: 0,
            EvidenceStatus.user_confirmed: 1,
            EvidenceStatus.ai_inferred: 2,
        }[item.evidence_status]
        reference_rank = 0 if item.source_reference else 1
        eligible.append(
            (
                relevance_rank,
                status_rank,
                reference_rank,
                str(item.id),
                item,
            )
        )

    selected: list[IdentifyEvidence] = []
    activity_counts: dict[str, int] = {}
    for *_, item in sorted(eligible, key=lambda candidate: candidate[:-1]):
        activity_key = item.source_activity or "unknown"
        if activity_counts.get(activity_key, 0) >= MAX_ITEMS_PER_ACTIVITY:
            continue
        selected.append(item)
        activity_counts[activity_key] = activity_counts.get(activity_key, 0) + 1
        if len(selected) >= max_items:
            break

    return [
        _context_item(item, retrieved_documents.get(item.source_reference or ""))
        for item in selected
    ]


def _context_item(item: IdentifyEvidence, document: Any | None) -> dict[str, Any]:
    source_url = item.source.url
    if source_url is None and document is not None:
        source_url = document.url

    context: dict[str, Any] = {
        "evidenceId": str(item.id),
        "sourceActivity": item.source_activity,
        "coverageAreaIds": list(item.coverage_area_ids),
        "claim": _bounded(item.claim, MAX_CLAIM_CHARS),
        "source": {
            "title": _bounded(item.source.title, MAX_SOURCE_CHARS),
            "type": item.source.source_type,
        },
        "evidenceStatus": item.evidence_status.value,
    }
    if item.summary:
        context["summary"] = _bounded(item.summary, MAX_SUMMARY_CHARS)
    if item.source_reference:
        context["sourceReference"] = _bounded(
            item.source_reference, MAX_REFERENCE_CHARS
        )
    if source_url is not None:
        context["source"]["url"] = str(source_url)
    if item.confidence is not None:
        context["confidence"] = item.confidence
    return context


def _bounded(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."
