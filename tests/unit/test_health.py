"""Tests for /health and /ready using fake dependency checks (no network, no Docker)."""

import asyncio

import httpx
import openai
from fastapi.testclient import TestClient

from app import __version__
from app.api.routes_health import _describe_error, build_readiness_checks
from app.config import Settings


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise ConnectionRefusedError("connection refused")


async def _hang() -> None:
    await asyncio.sleep(10)


def test_health_returns_ok_and_version(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_ready_is_200_when_all_dependencies_ok(client: TestClient) -> None:
    client.app.state.readiness_checks = {"qdrant": _ok, "postgres": _ok}
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert all(check["ok"] for check in body["checks"].values())


def test_ready_is_503_and_names_the_failing_dependency(client: TestClient) -> None:
    client.app.state.readiness_checks = {"qdrant": _ok, "postgres": _fail}
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["qdrant"]["ok"] is True
    assert body["checks"]["postgres"]["ok"] is False
    assert "connection refused" in body["checks"]["postgres"]["detail"]


def test_ready_times_out_slow_dependencies(client: TestClient) -> None:
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"health_check_timeout_s": 0.05}
    )
    client.app.state.readiness_checks = {"mlflow": _hang}
    response = client.get("/ready")
    assert response.status_code == 503
    assert "timed out" in response.json()["checks"]["mlflow"]["detail"]


async def test_default_checks_cover_every_dependency(settings: Settings) -> None:
    with_tracing = settings.model_copy(update={"tracing_enabled": True})
    async with httpx.AsyncClient() as http:
        checks = build_readiness_checks(with_tracing, http, openai_client=None)
    assert set(checks) == {"qdrant", "postgres", "mlflow", "openai"}


async def test_mlflow_is_not_checked_when_tracing_is_off(settings: Settings) -> None:
    no_tracing = settings.model_copy(update={"tracing_enabled": False})
    async with httpx.AsyncClient() as http:
        checks = build_readiness_checks(no_tracing, http, openai_client=None)
    assert set(checks) == {"qdrant", "postgres", "openai"}


async def test_openai_check_fails_clearly_without_api_key(settings: Settings) -> None:
    async with httpx.AsyncClient() as http:
        checks = build_readiness_checks(settings, http, openai_client=None)
        try:
            await checks["openai"]()
        except RuntimeError as exc:
            assert "OPENAI_API_KEY is not set" in str(exc)
        else:
            raise AssertionError("expected the openai check to fail without a key")


def test_openai_errors_never_echo_their_message() -> None:
    request = httpx.Request("GET", "https://api.openai.com/v1/models/x")
    response = httpx.Response(401, request=request)
    exc = openai.AuthenticationError("Incorrect API key sk-abc...xyz", response=response, body=None)
    assert _describe_error(exc) == "AuthenticationError (HTTP 401)"
