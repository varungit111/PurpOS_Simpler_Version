from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_detective import router as ai_detective_router
from app.api.alignment import router as alignment_router
from app.api.company_cards import router as company_cards_router
from app.api.conversation import router as conversation_router
from app.api.define import router as define_router
from app.api.discover_synthesis import router as discover_synthesis_router
from app.api.evidence_wall import router as evidence_wall_router
from app.api.health import router as health_router
from app.api.identify_brief import router as identify_brief_router
from app.api.listen_summary import router as listen_summary_router
from app.api.perception_gaps import router as perception_gaps_router
from app.api.sessions import router as sessions_router
from app.api.signal_hunt import router as signal_hunt_router
from app.api.stakeholder_journeys import router as stakeholder_journeys_router
from app.api.stakeholders import router as stakeholders_router
from app.api.stress_test import router as stress_test_router
from app.api.where_do_you_stand import router as where_do_you_stand_router
from app.config.settings import settings
from app.store.sessions import IdentifyStageReadOnlyError


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Foundation API for the PurpOS prototype.",
    )

    # CORS is kept narrow for local development. Production origins can be added
    # later through configuration without changing route code.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(IdentifyStageReadOnlyError)
    async def identify_review_only(
        _request: Request, exc: IdentifyStageReadOnlyError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(conversation_router)
    app.include_router(define_router)
    app.include_router(stress_test_router)
    app.include_router(alignment_router)
    app.include_router(discover_synthesis_router)
    app.include_router(ai_detective_router)
    app.include_router(company_cards_router)
    app.include_router(listen_summary_router)
    app.include_router(perception_gaps_router)
    app.include_router(stakeholders_router)
    app.include_router(stakeholder_journeys_router)
    app.include_router(signal_hunt_router)
    app.include_router(where_do_you_stand_router)
    app.include_router(evidence_wall_router)
    app.include_router(identify_brief_router)
    return app


app = create_app()
