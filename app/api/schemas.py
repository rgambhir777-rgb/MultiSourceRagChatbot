"""Pydantic models for API responses. They define the JSON contract clients rely on."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


# ------------------------------------------------------------------------------ ingestion


class GithubIngestRequest(BaseModel):
    """Body of POST /api/ingest/github."""

    url: str = Field(max_length=300, examples=["https://github.com/pallets/itsdangerous"])


class JobFileResult(BaseModel):
    file: str
    outcome: str
    chunks: int
    detail: str


class JobResponse(BaseModel):
    """An ingestion job: poll GET /api/jobs/{id} until status is succeeded or failed."""

    id: uuid.UUID
    kind: str
    target: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress_done: int
    progress_total: int
    summary: dict[str, int]
    results: list[JobFileResult]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class DocumentResponse(BaseModel):
    """One indexed document from the registry."""

    id: uuid.UUID
    source: str
    file_type: str
    chunk_count: int
    page_count: int | None
    size_bytes: int
    updated_at: datetime
