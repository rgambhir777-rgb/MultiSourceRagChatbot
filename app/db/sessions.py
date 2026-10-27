"""The `chat_sessions` table: the list of conversations shown in the UI sidebar."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row
from psycopg_pool import ConnectionPool

TITLE_MAX_CHARS = 60


@dataclass(frozen=True)
class SessionRecord:
    id: uuid.UUID
    title: str
    turn_count: int
    created_at: datetime
    updated_at: datetime


class SessionStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def create(self) -> SessionRecord:
        with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=class_row(SessionRecord)) as cur,
        ):
            cur.execute(
                "INSERT INTO chat_sessions (id) VALUES (%s) "
                "RETURNING id, title, turn_count, created_at, updated_at",
                (uuid.uuid4(),),
            )
            record = cur.fetchone()
        if record is None:  # pragma: no cover - INSERT ... RETURNING always returns the row
            raise RuntimeError("session insert returned no row")
        return record

    def get(self, session_id: uuid.UUID) -> SessionRecord | None:
        with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=class_row(SessionRecord)) as cur,
        ):
            cur.execute(
                "SELECT id, title, turn_count, created_at, updated_at FROM chat_sessions "
                "WHERE id = %s",
                (session_id,),
            )
            return cur.fetchone()

    def list_recent(self, limit: int) -> list[SessionRecord]:
        with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=class_row(SessionRecord)) as cur,
        ):
            cur.execute(
                "SELECT id, title, turn_count, created_at, updated_at FROM chat_sessions "
                "ORDER BY updated_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()

    def record_turn(self, session_id: uuid.UUID, question: str) -> None:
        """Count a finished turn; the first question becomes the conversation's title."""
        title = " ".join(question.split())[:TITLE_MAX_CHARS] or "New chat"
        with self._pool.connection() as conn:
            conn.execute(
                """
                UPDATE chat_sessions
                SET turn_count = turn_count + 1,
                    updated_at = now(),
                    title = CASE WHEN turn_count = 0 THEN %s ELSE title END
                WHERE id = %s
                """,
                (title, session_id),
            )

    def delete(self, session_id: uuid.UUID) -> bool:
        with self._pool.connection() as conn:
            return (
                conn.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,)).rowcount > 0
            )
