"""FastAPI application factory.

`create_app()` builds a fresh app from a Settings object. Tests call it with their own settings.
Uvicorn calls it with `--factory`:

    uvicorn app.main:create_app --factory --reload

The `lifespan` function runs once at startup (open shared clients) and once at shutdown (close
them), so connections are reused across requests instead of being opened per request.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import httpx
import structlog
from fastapi import FastAPI

from app import __version__
from app.agent.llm import make_openai_client
from app.api.routes_chat import router as chat_router
from app.api.routes_health import build_readiness_checks
from app.api.routes_health import router as health_router
from app.api.routes_ingest import router as ingest_router
from app.config import Settings, get_settings
from app.logging_setup import configure_logging
from app.observability.tracing import setup_tracing
from app.services import Services

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app with logging, shared clients and all routers."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=settings.app_env == "prod")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        http = httpx.AsyncClient(timeout=settings.health_check_timeout_s)
        openai_client = make_openai_client(settings)
        app.state.settings = settings
        app.state.readiness_checks = build_readiness_checks(settings, http, openai_client)
        app.state.services = Services(settings)  # models/pools are built on first use
        # set_experiment talks to the MLflow server: run it off the event loop.
        app.state.tracing = await anyio.to_thread.run_sync(setup_tracing, settings)
        log.info(
            "api_started",
            version=__version__,
            env=settings.app_env,
            openai_key_configured=openai_client is not None,
        )
        try:
            yield
        finally:
            app.state.services.close()
            await http.aclose()
            if openai_client is not None:
                await openai_client.close()
            log.info("api_stopped")

    app = FastAPI(title="MultiSource RAG Chatbot API", version=__version__, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(chat_router)
    return app
