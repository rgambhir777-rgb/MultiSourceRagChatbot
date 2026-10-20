"""Liveness (`/health`) and readiness (`/ready`) endpoints.

- `/health` answers "is the process alive?" It never touches dependencies, so it stays fast and
  only fails if the API itself is broken.
- `/ready` answers "can the API do its job right now?" It checks every dependency in parallel,
  each with a timeout, and returns 503 if any of them fails. Orchestrators (and humans) use it
  to decide whether to send traffic.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

import httpx
import openai
import psycopg
import structlog
from anyio import to_thread
from fastapi import APIRouter, Request, Response, status

from app import __version__
from app.api.schemas import DependencyStatus, HealthResponse, ReadinessResponse
from app.config import Settings

log = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])

# A readiness check is an async function that returns nothing on success and raises on failure.
ReadinessCheck = Callable[[], Awaitable[None]]


def build_readiness_checks(
    settings: Settings,
    http: httpx.AsyncClient,
    openai_client: openai.AsyncOpenAI | None,
) -> dict[str, ReadinessCheck]:
    """Create one check per dependency. Called once at startup; tests can swap these out."""

    async def check_qdrant() -> None:
        headers = {}
        if settings.qdrant_api_key is not None:
            headers["api-key"] = settings.qdrant_api_key.get_secret_value()
        response = await http.get(f"{settings.qdrant_url.rstrip('/')}/readyz", headers=headers)
        response.raise_for_status()

    async def check_postgres() -> None:
        # Uses the sync driver in a worker thread: psycopg's async mode needs a different
        # event loop on Windows. That is solved properly in Session 8, when we need async.
        def ping() -> None:
            connect_timeout = max(1, int(settings.health_check_timeout_s))
            with psycopg.connect(
                settings.postgres_conninfo, connect_timeout=connect_timeout
            ) as conn:
                conn.execute("SELECT 1")

        await to_thread.run_sync(ping, abandon_on_cancel=True)

    async def check_mlflow() -> None:
        response = await http.get(f"{settings.mlflow_tracking_uri.rstrip('/')}/health")
        response.raise_for_status()

    async def check_openai() -> None:
        if openai_client is None:
            raise RuntimeError("OPENAI_API_KEY is not set")
        # Looking up a model is free (no tokens). It proves the key works AND the model ID exists.
        models = {settings.llm_generator_model, settings.llm_judge_model}
        await asyncio.gather(*(openai_client.models.retrieve(model) for model in models))

    return {
        "qdrant": check_qdrant,
        "postgres": check_postgres,
        "mlflow": check_mlflow,
        "openai": check_openai,
    }


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Readiness probe: 200 if every dependency is reachable, otherwise 503 with details."""
    checks: dict[str, ReadinessCheck] = request.app.state.readiness_checks
    timeout_s: float = request.app.state.settings.health_check_timeout_s

    names = list(checks)
    results = await asyncio.gather(*(_run_check(name, checks[name], timeout_s) for name in names))
    all_ok = all(result.ok for result in results)
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        checks=dict(zip(names, results, strict=True)),
    )


async def _run_check(name: str, check: ReadinessCheck, timeout_s: float) -> DependencyStatus:
    """Run one check with a timeout and turn the outcome into a DependencyStatus."""
    started = time.perf_counter()
    detail: str | None = None
    try:
        await asyncio.wait_for(check(), timeout=timeout_s)
    except TimeoutError:
        detail = f"timed out after {timeout_s:g}s"
    except Exception as exc:  # any failure means "not ready"; the reason goes in `detail`
        detail = _describe_error(exc)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    if detail is not None:
        log.warning("readiness_check_failed", dependency=name, error=detail)
    return DependencyStatus(ok=detail is None, latency_ms=latency_ms, detail=detail)


def _describe_error(exc: Exception) -> str:
    """Short, safe error text. OpenAI error messages can echo part of the API key, so for
    those we report only the error type and HTTP status."""
    if isinstance(exc, openai.APIStatusError):
        return f"{type(exc).__name__} (HTTP {exc.status_code})"
    if isinstance(exc, openai.OpenAIError):
        return type(exc).__name__
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return f"{type(exc).__name__}: {exc}"[:200]
