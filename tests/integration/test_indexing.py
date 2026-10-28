"""End-to-end ingestion against the real Qdrant and Postgres (needs `docker compose up -d`).

Each test run uses its own throwaway Qdrant collection and Postgres schema, removed afterwards,
so the real knowledge base is never touched. Run with:  pytest -m integration
"""

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from psycopg import sql

from app.config import Settings
from app.db.pool import apply_schema, create_pool
from app.db.repositories import DocumentRegistry
from app.ingestion.pipeline import IngestionPipeline, Outcome, document_id
from app.retrieval.embeddings import Embedder
from app.retrieval.vectorstore import VectorStore

pytestmark = pytest.mark.integration

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_docs"
SAMPLE_CHUNKS = 23  # 5 (docx) + 2 (txt) + 14 (md) + 2 (pdf) at the default 400-token size


@pytest.fixture
def isolated() -> Iterator[tuple[IngestionPipeline, VectorStore, DocumentRegistry]]:
    name = f"test_{uuid.uuid4().hex[:10]}"
    settings = Settings(qdrant_collection=name, postgres_schema=name)
    embedder = Embedder(settings)
    store = VectorStore.from_settings(settings, embedder.dense_size)
    pool = create_pool(settings)  # creates the throwaway schema
    try:
        store.ensure_collection()
        apply_schema(pool)
        registry = DocumentRegistry(pool)
        yield IngestionPipeline(settings, embedder, store, registry), store, registry
    finally:
        store.drop_collection()
        with pool.connection() as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
        pool.close()
        store.close()


def test_ingest_skip_reindex_and_duplicate(isolated, tmp_path: Path) -> None:
    pipeline, store, registry = isolated
    docs = tmp_path / "docs"
    shutil.copytree(SAMPLES, docs)

    first = pipeline.ingest_paths([docs])
    assert [r.outcome for r in first] == [Outcome.INDEXED] * 4
    assert store.count() == SAMPLE_CHUNKS
    assert len(registry.list_all()) == 4

    second = pipeline.ingest_paths([docs])
    assert [r.outcome for r in second] == [Outcome.SKIPPED] * 4
    assert store.count() == SAMPLE_CHUNKS

    handbook = docs / "orbit_handbook.md"
    handbook.write_text("# Orbit T2\n\nThe handbook was rewritten and is now very short.\n")
    [changed] = pipeline.ingest_paths([handbook])
    assert changed.outcome is Outcome.REINDEXED
    assert changed.chunks == 1
    assert store.count(str(document_id("orbit_handbook.md"))) == 1, "old chunks were trimmed"
    assert store.count() == SAMPLE_CHUNKS - 14 + 1
    assert registry.find_by_source("orbit_handbook.md").chunk_count == 1

    copy = docs / "faq-copy.txt"
    shutil.copy(docs / "orbit_faq.txt", copy)
    [duplicate] = pipeline.ingest_paths([copy])
    assert duplicate.outcome is Outcome.DUPLICATE
    assert store.count() == SAMPLE_CHUNKS - 14 + 1
