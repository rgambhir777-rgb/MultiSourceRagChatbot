"""The `ingest_jobs` table: create jobs, track their progress and record their results."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from psycopg.rows import class_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

JobKind = Literal["files", "github"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]

_SELECT_JOBS = """
    SELECT id, kind, target, status, progress_done, progress_total, summary, results, error,
           created_at, started_at, finished_at
    FROM ingest_jobs
"""


@dataclass(frozen=True)
class JobRecord:
    """One row of the `ingest_jobs` table."""

    id: uuid.UUID
    kind: str
    target: str
    status: str
    progress_done: int
    progress_total: int
    summary: dict[str, int]
    results: list[dict[str, Any]]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobStore:
    """Small, named operations on ingestion jobs (each in its own short transaction)."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def create(self, kind: JobKind, target: str) -> JobRecord:
        with self._pool.connection() as conn, conn.cursor(row_factory=class_row(JobRecord)) as cur:
            cur.execute(
                """
                INSERT INTO ingest_jobs (id, kind, target, status) VALUES (%s, %s, %s, 'queued')
                RETURNING id, kind, target, status, progress_done, progress_total, summary,
                          results, error, created_at, started_at, finished_at
                """,
                (uuid.uuid4(), kind, target),
            )
            record = cur.fetchone()
        if record is None:  # pragma: no cover - INSERT ... RETURNING always returns the row
            raise RuntimeError("job insert returned no row")
        return record

    def get(self, job_id: uuid.UUID) -> JobRecord | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=class_row(JobRecord)) as cur:
            cur.execute(_SELECT_JOBS + "WHERE id = %s", (job_id,))
            return cur.fetchone()

    def list_recent(self, limit: int) -> list[JobRecord]:
        with self._pool.connection() as conn, conn.cursor(row_factory=class_row(JobRecord)) as cur:
            cur.execute(_SELECT_JOBS + "ORDER BY created_at DESC LIMIT %s", (limit,))
            return cur.fetchall()

    def mark_running(self, job_id: uuid.UUID) -> None:
        self._execute(
            "UPDATE ingest_jobs SET status = 'running', started_at = now() WHERE id = %s",
            (job_id,),
        )

    def update_progress(self, job_id: uuid.UUID, done: int, total: int) -> None:
        self._execute(
            "UPDATE ingest_jobs SET progress_done = %s, progress_total = %s WHERE id = %s",
            (done, total, job_id),
        )

    def finish(
        self, job_id: uuid.UUID, summary: dict[str, int], results: Sequence[dict[str, Any]]
    ) -> None:
        self._execute(
            """
            UPDATE ingest_jobs
            SET status = 'succeeded', summary = %s, results = %s, finished_at = now()
            WHERE id = %s
            """,
            (Jsonb(summary), Jsonb(list(results)), job_id),
        )

    def fail(self, job_id: uuid.UUID, error: str) -> None:
        self._execute(
            "UPDATE ingest_jobs SET status = 'failed', error = %s, finished_at = now() "
            "WHERE id = %s",
            (error, job_id),
        )

    def fail_interrupted(self) -> int:
        """Mark jobs left unfinished by a previous process (crash/restart) as failed."""
        with self._pool.connection() as conn:
            cursor = conn.execute(
                """
                UPDATE ingest_jobs
                SET status = 'failed',
                    error = 'interrupted: the server restarted',
                    finished_at = now()
                WHERE status IN ('queued', 'running')
                """
            )
            return cursor.rowcount

    def _execute(self, query: str, params: tuple[object, ...]) -> None:
        with self._pool.connection() as conn:
            conn.execute(query, params)
