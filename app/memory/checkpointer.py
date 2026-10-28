"""Persistent conversation memory with LangGraph's Postgres *checkpointer*.

After every step of the agent, LangGraph saves a *checkpoint* (a snapshot of the state, incl.
the whole conversation) under a `thread_id`. We use the chat session id as the thread id, so
a conversation can continue after the API restarts: the next message simply loads the latest
checkpoint of that thread.

This is LangGraph's synchronous saver. Each chat turn runs in a worker thread (see
app/api/routes_chat.py), so the Windows async-driver issue never arises.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import Settings
from app.db.pool import ensure_schema

# Checkpoints are loaded back into Python objects. Only types listed here may be rebuilt, so
# a tampered database row can't make the app construct arbitrary classes.
ALLOWED_STATE_TYPES = [("app.retrieval.retriever", "RetrievedChunk")]
CHECKPOINT_POOL_SIZE = 3


def create_checkpointer(settings: Settings) -> tuple[PostgresSaver, ConnectionPool]:
    """Return a ready checkpointer (tables created) and its pool (close it at shutdown).

    The saver needs autocommit, no prepared statements and dict rows, which differ from the
    app's own pool, so it gets a small pool of its own.
    """
    kwargs: dict[str, object] = {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        "connect_timeout": settings.postgres_connect_timeout_s,
    }
    if settings.postgres_schema != "public":
        kwargs["options"] = f"-c search_path={settings.postgres_schema}"
    pool = ConnectionPool(
        settings.postgres_conninfo,
        min_size=1,
        max_size=CHECKPOINT_POOL_SIZE,
        kwargs=kwargs,
        open=True,
        name="ragbot-checkpoints",
        check=ConnectionPool.check_connection,  # survive Postgres restarts (see app/db/pool.py)
    )
    pool.wait(timeout=settings.postgres_connect_timeout_s)
    ensure_schema(pool, settings.postgres_schema)
    saver = PostgresSaver(
        pool, serde=JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_STATE_TYPES)
    )
    saver.setup()  # creates/migrates LangGraph's checkpoint tables (idempotent)
    return saver, pool
