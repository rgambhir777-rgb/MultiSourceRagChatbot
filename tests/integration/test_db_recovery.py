"""The connection pools recover by themselves after Postgres drops their connections.

Reproduces a real bug found while building the CI pipeline: after the Postgres container was
recreated, the running API kept handing out dead pooled connections and answered 500 until it
was restarted. Run with:  pytest -m integration
"""

import psycopg
import pytest

from app.config import Settings
from app.db.pool import create_pool
from app.memory.checkpointer import create_checkpointer

pytestmark = pytest.mark.integration


def _drop_all_connections(settings: Settings, application_name_like: str) -> int:
    """Ask Postgres to close every connection of our pools (like a database restart)."""
    with psycopg.connect(settings.postgres_conninfo, autocommit=True) as admin:
        return admin.execute(
            "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
            "AND application_name LIKE %s",
            (application_name_like,),
        ).fetchone()[0]


def test_app_pool_recovers_after_connections_are_dropped() -> None:
    settings = Settings()
    pool = create_pool(settings)
    try:
        with pool.connection() as conn:
            conn.execute("SET application_name = 'recovery-test-app'")
            assert conn.execute("SELECT 1").fetchone() == (1,)
        assert _drop_all_connections(settings, "recovery-test-app") >= 1
        with pool.connection() as conn:  # must get a fresh, working connection
            assert conn.execute("SELECT 2").fetchone() == (2,)
    finally:
        pool.close()


def test_checkpointer_pool_recovers_after_connections_are_dropped() -> None:
    settings = Settings()
    _saver, pool = create_checkpointer(settings)
    try:
        with pool.connection() as conn:
            conn.execute("SET application_name = 'recovery-test-cp'")
        assert _drop_all_connections(settings, "recovery-test-cp") >= 1
        with pool.connection() as conn:
            assert conn.execute("SELECT 3 AS value").fetchone()["value"] == 3
    finally:
        pool.close()
