from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.ai_detective import (
    AIDetectiveProgress,
    AIDetectiveResponse,
    AIDetectiveUpdateRequest,
)
from app.schemas.assessment import ExternalResearchState, ResearchFinding
from app.services.ai_client import (
    AIClient,
    AIProviderError,
    MissingAIAPIKeyError,
    create_ai_client,
)
from app.services.research import IdentifyEvidenceResearchProvider
from app.store.sessions import session_store

router = APIRouter(prefix="/api/sessions", tags=["ai-detective"])


@router.get(
    "/{session_id}/identify/ai-detective",
    response_model=AIDetectiveResponse,
)
def get_ai_detective(session_id: UUID) -> AIDetectiveResponse:
    state = session_store.get_identify_state(session_id)
    if state is None:
        raise _session_not_found()

    return _response(
        state.output.research_findings,
        external_research=state.output.external_research,
    )


@router.put(
    "/{session_id}/identify/ai-detective",
    response_model=AIDetectiveResponse,
)
def update_ai_detective(
    session_id: UUID, payload: AIDetectiveUpdateRequest
) -> AIDetectiveResponse:
    state = session_store.update_identify_research_findings(
        session_id=session_id,
        findings=payload.findings,
    )
    if state is None:
        raise _session_not_found()

    return _response(
        state.output.research_findings,
        message="AI Detective review saved.",
        external_research=state.output.external_research,
    )


@router.post(
    "/{session_id}/identify/ai-detective/collect",
    response_model=AIDetectiveResponse,
)
def collect_ai_detective(
    session_id: UUID,
    refresh: bool = Query(default=False),
) -> AIDetectiveResponse:
    session = session_store.get(session_id)
    if session is None:
        raise _session_not_found()

    provider = _get_research_provider()
    result = provider.collect(
        session.identify,
        organisation=session.organisation,
        refresh=refresh,
    )
    if result.external_research is not None:
        updated = session_store.update_identify_ai_detective_research(
            session_id=session_id,
            findings=result.findings,
            external_research=result.external_research,
        )
        if updated is None:
            raise _session_not_found()
        return _response(
            updated.output.research_findings,
            research_status=result.status,
            message=result.message,
            external_research=updated.output.external_research,
        )

    return _response(
        result.findings,
        research_status=result.status,
        message=result.message,
        external_research=session.identify.output.external_research,
    )


def _get_ai_client() -> AIClient | None:
    try:
        return create_ai_client()
    except MissingAIAPIKeyError:
        return None
    except AIProviderError:
        return None


def _get_research_provider() -> IdentifyEvidenceResearchProvider:
    return IdentifyEvidenceResearchProvider(ai_client=_get_ai_client())


def _response(
    findings: list[ResearchFinding],
    research_status: str = "idle",
    message: str | None = None,
    external_research: ExternalResearchState | None = None,
) -> AIDetectiveResponse:
    count = len(findings)
    label = (
        "No research findings reviewed yet"
        if count == 0
        else f"{count} finding{'s' if count != 1 else ''} reviewed"
    )
    return AIDetectiveResponse(
        research_status=research_status,
        progress=AIDetectiveProgress(
            findingsCount=count,
            label=label,
            limitation=_research_limitation(external_research),
        ),
        findings=findings,
        externalResearch=external_research or ExternalResearchState(),
        message=message,
    )


def _research_limitation(external_research: ExternalResearchState | None) -> str | None:
    if external_research is None:
        return None
    unscanned = [
        category.category
        for category in external_research.categories
        if category.status in {"not-scanned", "not-configured"}
    ]
    if not unscanned:
        return None
    return (
        "First-party category coverage reflects retrieved company website pages. "
        "Broader external search categories are not scanned because no approved "
        "search provider is configured."
    )


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Assessment session not found.",
    )
