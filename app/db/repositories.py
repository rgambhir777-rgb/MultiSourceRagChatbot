"""Small, named SQL functions for the `documents` table (the "document registry").

Each function takes an open connection, so the caller decides the transaction boundary
(`with pool.connection() as conn:` commits everything inside it together).
Values are always passed as query parameters (`%s`), never pasted into the SQL string, which
is what prevents SQL injection.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from psycopg import Connection
from psycopg.rows import class_row
from psycopg_pool import ConnectionPool

# Every query is a fixed string; only values vary, passed separately as parameters.
_SELECT_DOCUMENTS = """
    SELECT id, source, file_type, content_hash, size_bytes, page_count, chunk_count,
           created_at, updated_at
    FROM documents
"""


@dataclass(frozen=True)
class DocumentRecord:
    """One row of the `documents` table."""

    id: uuid.UUID
    source: str
    file_type: str
    content_hash: str
    size_bytes: int
    page_count: int | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


def get_document_by_source(conn: Connection, source: str) -> DocumentRecord | None:
    with conn.cursor(row_factory=class_row(DocumentRecord)) as cur:
        cur.execute(_SELECT_DOCUMENTS + "WHERE source = %s", (source,))
        return cur.fetchone()


def get_document_by_hash(conn: Connection, content_hash: str) -> DocumentRecord | None:
    with conn.cursor(row_factory=class_row(DocumentRecord)) as cur:
        cur.execute(
            _SELECT_DOCUMENTS + "WHERE content_hash = %s ORDER BY created_at LIMIT 1",
            (content_hash,),
        )
        return cur.fetchone()


def list_documents(conn: Connection) -> list[DocumentRecord]:
    with conn.cursor(row_factory=class_row(DocumentRecord)) as cur:
        cur.execute(_SELECT_DOCUMENTS + "ORDER BY source")
        return cur.fetchall()


def upsert_document(
    conn: Connection,
    *,
    doc_id: uuid.UUID,
    source: str,
    file_type: str,
    content_hash: str,
    size_bytes: int,
    page_count: int | None,
    chunk_count: int,
) -> None:
    """Insert a document, or update it if this source is already registered."""
    conn.execute(
        """
        INSERT INTO documents
            (id, source, file_type, content_hash, size_bytes, page_count, chunk_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source) DO UPDATE SET
            file_type    = EXCLUDED.file_type,
            content_hash = EXCLUDED.content_hash,
            size_bytes   = EXCLUDED.size_bytes,
            page_count   = EXCLUDED.page_count,
            chunk_count  = EXCLUDED.chunk_count,
            updated_at   = now()
        """,
        (doc_id, source, file_type, content_hash, size_bytes, page_count, chunk_count),
    )


class DocumentRegistry:
    """The document registry as one object, so the ingestion pipeline depends on these few
    methods (easy to replace with a fake in unit tests) rather than on database details."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def find_by_source(self, source: str) -> DocumentRecord | None:
        with self._pool.connection() as conn:
            return get_document_by_source(conn, source)

    def find_by_hash(self, content_hash: str) -> DocumentRecord | None:
        with self._pool.connection() as conn:
            return get_document_by_hash(conn, content_hash)

    def list_all(self) -> list[DocumentRecord]:
        with self._pool.connection() as conn:
            return list_documents(conn)

    def save(
        self,
        *,
        doc_id: uuid.UUID,
        source: str,
        file_type: str,
        content_hash: str,
        size_bytes: int,
        page_count: int | None,
        chunk_count: int,
    ) -> None:
        with self._pool.connection() as conn:
            upsert_document(
                conn,
                doc_id=doc_id,
                source=source,
                file_type=file_type,
                content_hash=content_hash,
                size_bytes=size_bytes,
                page_count=page_count,
                chunk_count=chunk_count,
            )
