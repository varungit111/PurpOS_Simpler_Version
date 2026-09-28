import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.assessment import PESTLECategory, PESTLEFinding
from app.schemas.signal_hunt import (
    SignalHuntGeneration,
    SignalHuntProgress,
    SignalHuntResponse,
    SignalHuntUpdateRequest,
)
from app.services.ai_client import (
    AIClient,
    AIClientError,
    AIProviderError,
    MissingAIAPIKeyError,
    create_ai_client,
)
from app.services.identify_evidence_context import build_identify_evidence_context
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["signal-hunt"])

SIGNAL_HUNT_SYSTEM = """
You support the PurpOS Identify stage. Generate PESTLE findings for Signal Hunt
as an external-environment analysis framework, not as six mandatory questions or
separate activity agents. Use available organisation context, SME answers,
Identify evidence, stakeholder context and existing findings. Return concise,
evidence-aware findings only in the requested schema. Do not invent numeric
strength, severity or confidence formulas. Use only the six supplied PESTLE
categories, and return only findings supported by the supplied assessment
evidence. It is acceptable to leave categories uncovered. Company statements
are context, not independent proof of an external trend. Preserve supplied
provenance and never imply that wider public-web research occurred.
""".strip()

PESTLE_AREA_IDS = {
    "political_context",
    "economic_context",
    "social_context",
    "technology_context",
    "legal_context",
    "environmental_context",
}


@router.get(
    "/{session_id}/identify/signal-hunt",
    response_model=SignalHuntResponse,
)
def get_signal_hunt(session_id: UUID) -> SignalHuntResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(state.output.pestle_findings)


@router.put(
    "/{session_id}/identify/signal-hunt",
    response_model=SignalHuntResponse,
)
def update_signal_hunt(
    session_id: UUID, payload: SignalHuntUpdateRequest
) -> SignalHuntResponse:
    state = session_store.update_identify_pestle_findings(
        session_id=session_id,
        findings=payload.findings,
    )
    if state is None:
        raise _session_not_found()

    return _response(
        state.output.pestle_findings,
        message="Signal Hunt review saved.",
    )


@router.post(
    "/{session_id}/identify/signal-hunt/generate",
    response_model=SignalHuntResponse,
)
def generate_signal_hunt(session_id: UUID) -> SignalHuntResponse:
    session = session_store.get(session_id)
    if session is None:
        raise _session_not_found()
    state = session.identify

    ai_client, ai_status = _get_ai_client()
    if ai_client is None:
        return _response(
            state.output.pestle_findings,
            ai_status=ai_status,
            message=(
                "AI analysis is unavailable. Existing Signal Hunt findings "
                "are unchanged."
            ),
        )

    try:
        generation = ai_client.generate_structured(
            prompt=_build_signal_hunt_prompt(
                state.output.pestle_findings,
                evidence_context=build_identify_evidence_context(
                    state,
                    source_activities={
                        "ai-detective",
                        "who-matters",
                        "hot-seat",
                        "company-cards",
                        "day-in-their-shoes",
                        "where-do-you-stand",
                    },
                    preferred_area_ids=PESTLE_AREA_IDS,
                ),
                company_name=session.organisation.company_name,
                website=(
                    str(session.organisation.website)
                    if session.organisation.website is not None
                    else None
                ),
            ),
            output_schema=SignalHuntGeneration,
            system=SIGNAL_HUNT_SYSTEM,
        )
    except AIClientError:
        return _response(
            state.output.pestle_findings,
            ai_status="error",
            message=(
                "AI analysis could not complete. Existing Signal Hunt findings "
                "are unchanged."
            ),
        )

    updated = session_store.update_identify_pestle_findings(
        session_id=session_id,
        findings=generation.findings,
    )
    if updated is None:
        raise _session_not_found()

    return _response(
        updated.output.pestle_findings,
        ai_status=ai_status,
        message="Signal Hunt findings generated for review.",
    )


def _get_ai_client() -> tuple[AIClient | None, str]:
    try:
        return create_ai_client(), "connected"
    except MissingAIAPIKeyError:
        return None, "unavailable"
    except AIProviderError:
        return None, "unavailable"


def _build_signal_hunt_prompt(
    existing_findings: list[PESTLEFinding],
    evidence_context: list[dict[str, object]] | None = None,
    company_name: str | None = None,
    website: str | None = None,
) -> str:
    categories = ", ".join(category.value for category in PESTLECategory)
    organisation = {
        "companyName": company_name,
        "website": website,
    }
    existing = [
        {
            "category": finding.category.value,
            "signal": finding.signal,
            "description": finding.description,
            "whyItMatters": finding.why_it_matters,
            "opportunityOrRisk": finding.opportunity_or_risk,
            "evidenceSources": [
                source.model_dump(mode="json", by_alias=True)
                for source in finding.evidence_sources
            ],
        }
        for finding in existing_findings
    ]

    return (
        "Analyse the Identify evidence currently available for Signal Hunt. "
        f"Organisation context: {json.dumps(organisation, separators=(',', ':'))}. "
        "Use these PESTLE categories as lenses, without forcing one finding per "
        f"category: {categories}. Look for longer-term external signals, trends, "
        "risks and opportunities that could affect future SOI options. Internal "
        "or company-website claims are useful company context but do not by "
        "themselves prove a wider external trend. Keep source types, labels, "
        "URLs and references attached to the claims they support. Do not imply "
        "broader web research. Return no finding for a category that lacks "
        "enough evidence. Compact evidence from this assessment only: "
        f"{json.dumps(evidence_context or [], separators=(',', ':'))}. "
        "Existing reviewed findings to consider: "
        f"{json.dumps(existing, separators=(',', ':'))}"
    )


def _response(
    findings: list[PESTLEFinding],
    ai_status: str = "idle",
    message: str | None = None,
) -> SignalHuntResponse:
    categories_covered = sorted(
        {finding.category for finding in findings},
        key=lambda category: category.value,
    )
    count = len(findings)
    label = (
        "No signals reviewed yet"
        if count == 0
        else f"{count} signal{'s' if count != 1 else ''} reviewed"
    )
    return SignalHuntResponse(
        ai_status=ai_status,
        progress=SignalHuntProgress(
            findingsCount=count,
            categoriesCovered=categories_covered,
            label=label,
        ),
        findings=findings,
        message=message,
    )


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
