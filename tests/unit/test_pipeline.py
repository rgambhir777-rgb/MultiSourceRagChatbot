"""Tests for the ingestion pipeline's decisions, using in-memory fakes for the embedder, Qdrant
and Postgres (no models, no Docker): what gets indexed, skipped, re-indexed or rejected."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.config import Settings
from app.db.repositories import DocumentRecord
from app.ingestion.models import Chunk
from app.ingestion.pipeline import (
    IngestionPipeline,
    Outcome,
    discover_files,
    document_id,
    text_for_embedding,
)
from app.retrieval.embeddings import EmbeddedTexts, SparseVector


class FakeEmbedder:
    def embed_passages(self, texts: Sequence[str]) -> EmbeddedTexts:
        return EmbeddedTexts(
            dense=[[0.1, 0.2] for _ in texts], sparse=[SparseVector([1], [1.0]) for _ in texts]
        )


class FakeStore:
    def __init__(self) -> None:
        self.chunks: dict[str, dict[int, Chunk]] = {}
        self.fail = False

    def upsert_chunks(self, doc_id: str, chunks: Sequence[Chunk], vectors: EmbeddedTexts) -> int:
        if self.fail:
            raise ConnectionError("qdrant unreachable")
        assert len(vectors.dense) == len(chunks)
        self.chunks.setdefault(doc_id, {}).update({c.chunk_index: c for c in chunks})
        return len(chunks)

    def delete_chunks_from(self, doc_id: str, first_index: int) -> None:
        stored = self.chunks.get(doc_id, {})
        for index in [i for i in stored if i >= first_index]:
            del stored[index]


class FakeRegistry:
    def __init__(self) -> None:
        self.rows: dict[str, DocumentRecord] = {}

    def find_by_source(self, source: str) -> DocumentRecord | None:
        return self.rows.get(source)

    def find_by_hash(self, content_hash: str) -> DocumentRecord | None:
        return next((r for r in self.rows.values() if r.content_hash == content_hash), None)

    def save(self, *, doc_id: uuid.UUID, source: str, **fields: object) -> None:
        now = datetime.now(UTC)
        self.rows[source] = DocumentRecord(
            id=doc_id,
            source=source,
            created_at=now,
            updated_at=now,
            **fields,  # type: ignore[arg-type]
        )


@pytest.fixture
def small_chunks(settings: Settings) -> Settings:
    return settings.model_copy(update={"chunk_size_tokens": 40, "chunk_overlap_tokens": 5})


@pytest.fixture
def parts(small_chunks: Settings) -> tuple[IngestionPipeline, FakeStore, FakeRegistry]:
    store, registry = FakeStore(), FakeRegistry()
    pipeline = IngestionPipeline(small_chunks, FakeEmbedder(), store, registry)  # type: ignore[arg-type]
    return pipeline, store, registry


def _write(path: Path, paragraphs: int) -> Path:
    path.write_text(
        "\n\n".join(f"Paragraph {i} about thermostats and wiring." for i in range(paragraphs))
    )
    return path


def test_new_file_is_indexed_and_registered(parts, tmp_path: Path) -> None:
    pipeline, store, registry = parts
    result = pipeline.ingest_file(_write(tmp_path / "guide.md", 10))
    assert result.outcome is Outcome.INDEXED
    doc_id = str(document_id("guide.md"))
    assert len(store.chunks[doc_id]) == result.chunks > 1
    assert registry.rows["guide.md"].chunk_count == result.chunks


def test_unchanged_file_is_skipped(parts, tmp_path: Path) -> None:
    pipeline, _, _ = parts
    path = _write(tmp_path / "guide.md", 10)
    pipeline.ingest_file(path)
    second = pipeline.ingest_file(path)
    assert second.outcome is Outcome.SKIPPED
    assert second.detail == "unchanged"


def test_changed_file_is_reindexed_and_old_extra_chunks_removed(parts, tmp_path: Path) -> None:
    pipeline, store, registry = parts
    path = _write(tmp_path / "guide.md", 20)
    first = pipeline.ingest_file(path)
    _write(path, 4)  # the file got much shorter
    second = pipeline.ingest_file(path)
    assert second.outcome is Outcome.REINDEXED
    assert second.chunks < first.chunks
    stored = store.chunks[str(document_id("guide.md"))]
    assert sorted(stored) == list(range(second.chunks)), "no stale chunks left behind"
    assert registry.rows["guide.md"].chunk_count == second.chunks


def test_same_content_under_another_name_is_a_duplicate(parts, tmp_path: Path) -> None:
    pipeline, store, _ = parts
    pipeline.ingest_file(_write(tmp_path / "guide.md", 5))
    result = pipeline.ingest_file(_write(tmp_path / "copy-of-guide.md", 5))
    assert result.outcome is Outcome.DUPLICATE
    assert "guide.md" in result.detail
    assert list(store.chunks) == [str(document_id("guide.md"))]


def test_bad_files_fail_without_stopping_the_others(parts, tmp_path: Path) -> None:
    pipeline, _, _ = parts
    (tmp_path / "empty.txt").write_text("")
    bad_type = tmp_path / "data.csv"
    bad_type.write_text("a,b")
    good = _write(tmp_path / "good.md", 3)
    results = pipeline.ingest_paths([tmp_path / "empty.txt", bad_type, good])
    assert [r.outcome for r in results] == [Outcome.FAILED, Outcome.FAILED, Outcome.INDEXED]
    assert "no text" in results[0].detail
    assert "not supported" in results[1].detail


def test_infrastructure_errors_are_reported_per_file(parts, tmp_path: Path) -> None:
    pipeline, store, registry = parts
    store.fail = True
    [result] = pipeline.ingest_paths([_write(tmp_path / "guide.md", 3)])
    assert result.outcome is Outcome.FAILED
    assert "ConnectionError" in result.detail
    assert registry.rows == {}, "the registry is only written after the chunks are stored"


def test_discover_files_expands_folders_and_keeps_explicit_files(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    for name in ("b.md", "a.pdf", "sub/c.txt", "skip.csv", ".hidden.md"):
        (tmp_path / name).write_text("x")
    explicit = tmp_path / "skip.csv"
    found = discover_files([tmp_path, explicit], [".md", ".pdf", ".txt"])
    names = [p.relative_to(tmp_path).as_posix() for p in found]
    assert names == ["a.pdf", "b.md", "sub/c.txt", "skip.csv"]


def test_text_for_embedding_adds_source_and_section() -> None:
    chunk = Chunk(
        text="Push each wire in.",
        source="handbook.md",
        file_type=".md",
        section="Installation > Wiring",
        chunk_index=0,
        token_count=5,
        content_hash="c",
        doc_hash="d",
    )
    assert text_for_embedding(chunk) == "handbook.md > Installation > Wiring\n\nPush each wire in."
    no_section = Chunk(**{**chunk.__dict__, "section": ""})
    assert text_for_embedding(no_section) == "handbook.md\n\nPush each wire in."


def test_document_id_is_deterministic() -> None:
    assert document_id("a.md") == document_id("a.md")
    assert document_id("a.md") != document_id("b.md")
