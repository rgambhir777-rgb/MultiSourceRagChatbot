"""Pydantic models for API responses. They define the JSON contract clients rely on."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness: the process is up and serving HTTP."""

    status: Literal["ok"] = "ok"
    version: str


class DependencyStatus(BaseModel):
    """Result of checking one dependency (database, vector store, LLM provider...)."""

    ok: bool
    latency_ms: float
    detail: str | None = None


class ReadinessResponse(BaseModel):
    """Readiness: every dependency the API needs is reachable."""

    status: Literal["ok", "degraded"]
    checks: dict[str, DependencyStatus]
