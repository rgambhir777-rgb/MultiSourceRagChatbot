"""PostgreSQL connection pool.

Opening a database connection is slow (network round-trips, login). A *pool* opens a few
connections once and lends them out: `with pool.connection() as conn: ...` borrows one, and
returns it at the end of the block (committing the transaction, or rolling back on error).

This is the synchronous pool, used by the CLI and background ingestion. The async API work
in Session 8 adds an async pool.
"""

from pathlib import Path

import structlog
from psycopg import sql
from psycopg_pool import ConnectionPool

from app.config import Settings

log = structlog.get_logger(__name__)

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def create_pool(settings: Settings, schema: str | None = None) -> ConnectionPool:
    """Open a pool and fail fast if the database can't be reached.

    `schema` (default: POSTGRES_SCHEMA) points every connection at a Postgres schema; tests use
    an isolated, throwaway one instead of the real tables. The schema is created if missing.
    """
    schema = schema or settings.postgres_schema
    connect_kwargs: dict[str, object] = {"connect_timeout": settings.postgres_connect_timeout_s}
    if schema != "public":
        connect_kwargs["options"] = f"-c search_path={schema}"
    pool = ConnectionPool(
        settings.postgres_conninfo,
        min_size=1,
        max_size=settings.postgres_pool_max_size,
        kwargs=connect_kwargs,
        open=True,
        name="ragbot",
        # Test each connection before lending it out and replace dead ones, so the app
        # recovers by itself when Postgres restarts (otherwise every query fails until the
        # API is restarted too).
        check=ConnectionPool.check_connection,
    )
    pool.wait(timeout=settings.postgres_connect_timeout_s)  # raises PoolTimeout if DB is down
    ensure_schema(pool, schema)
    return pool


def ensure_schema(pool: ConnectionPool, schema: str) -> None:
    """Create a non-default Postgres schema if it doesn't exist yet (safe to repeat)."""
    if schema != "public":
        with pool.connection() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))


def apply_schema(pool: ConnectionPool) -> None:
    """Create any missing tables/indexes. Safe to call on every start."""
    with pool.connection() as conn:
        conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    log.info("db_schema_applied")
