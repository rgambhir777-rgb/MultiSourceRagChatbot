"""The ingestion pipeline: files in, searchable chunks out.

For each file:  load → unchanged? skip → duplicate? skip → chunk → embed → store → register.

Two stores must stay consistent: Qdrant (the chunks) and Postgres (the document registry).
The registry row is written LAST, only after Qdrant holds every chunk. If anything fails in
between, the registry still shows the old fingerprint (or nothing), so the next run simply
re-indexes the file. Deterministic point IDs make that re-run overwrite instead of duplicate.
"""

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import structlog

from app.config import Settings
from app.db.pool import apply_schema, create_pool
from app.db.repositories import DocumentRegistry
from app.ingestion.chunking import SECTION_SEPARATOR, chunk_document
from app.ingestion.loaders import IngestionError, load_document
from app.ingestion.models import Chunk, LoadedDocument
from app.retrieval.embeddings import Embedder
from app.retrieval.vectorstore import VectorStore

log = structlog.get_logger(__name__)

# Fixed namespace: the same source name always maps to the same document id.
_DOCUMENT_NAMESPACE = uuid.UUID("2b7e9d14-5c3a-4e8f-a1b6-7d9c0e3f4a52")


class Outcome(StrEnum):
    INDEXED = "indexed"  # new document
    REINDEXED = "reindexed"  # known document whose content changed
    SKIPPED = "skipped"  # unchanged since last time
    DUPLICATE = "duplicate"  # same content already indexed under another name
    FAILED = "failed"


@dataclass(frozen=True)
class FileResult:
    """What happened to one file, for the CLI (and later the API) to report."""

    path: Path
    outcome: Outcome
    chunks: int = 0
    detail: str = ""


def document_id(source: str) -> uuid.UUID:
    """Deterministic document id derived from the source name."""
    return uuid.uuid5(_DOCUMENT_NAMESPACE, source)


def text_for_embedding(chunk: Chunk) -> str:
    """Prefix the chunk with where it comes from, so the vector knows its context.

    "Push each wire in until the button pops up" means far more to search when the vector also
    sees "orbit_handbook.md > Installation > Wiring the base plate". The stored payload keeps
    the original text for display.
    """
    header = SECTION_SEPARATOR.join(part for part in (chunk.source, chunk.section) if part)
    return f"{header}\n\n{chunk.text}"


def discover_files(paths: Sequence[Path], allowed_types: Sequence[str]) -> list[Path]:
    """Expand folders into the supported files inside them (recursively, sorted).

    Paths given explicitly are kept even if unsupported, so the user gets a clear "not
    supported" result instead of the file being silently ignored.
    """
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(
                sorted(
                    p
                    for p in path.rglob("*")
                    if p.is_file()
                    and p.suffix.lower() in allowed_types
                    and not p.name.startswith(".")
                )
            )
        else:
            found.append(path)
    return found


class IngestionPipeline:
    """Wires the loader, chunker, embedder, vector store and registry together."""

    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        store: VectorStore,
        registry: DocumentRegistry,
    ) -> None:
        self._settings = settings
        self._embedder = embedder
        self._store = store
        self._registry = registry

    def ingest_paths(self, paths: Sequence[Path]) -> list[FileResult]:
        """Ingest every file; one failing file never stops the others."""
        results = []
        for path in discover_files(paths, self._settings.allowed_file_types):
            try:
                result = self.ingest_file(path)
            except Exception as exc:  # infrastructure errors (DB/Qdrant down): report per file
                log.exception("ingest_failed", path=str(path))
                result = FileResult(path, Outcome.FAILED, detail=f"{type(exc).__name__}: {exc}")
            log.info("ingest_result", path=str(path), outcome=result.outcome, chunks=result.chunks)
            results.append(result)
        return results

    def ingest_file(self, path: Path) -> FileResult:
        try:
            document = load_document(path, self._settings)
        except (IngestionError, OSError) as exc:
            return FileResult(path, Outcome.FAILED, detail=str(exc))

        existing = self._registry.find_by_source(document.source)
        if existing is not None and existing.content_hash == document.content_hash:
            return FileResult(path, Outcome.SKIPPED, existing.chunk_count, "unchanged")
        if existing is None:
            duplicate = self._registry.find_by_hash(document.content_hash)
            if duplicate is not None:
                detail = f"same content already indexed as {duplicate.source}"
                return FileResult(path, Outcome.DUPLICATE, detail=detail)

        doc_id = existing.id if existing is not None else document_id(document.source)
        chunk_count = self._index(doc_id, document)
        outcome = Outcome.REINDEXED if existing is not None else Outcome.INDEXED
        return FileResult(path, outcome, chunk_count)

    def _index(self, doc_id: uuid.UUID, document: LoadedDocument) -> int:
        """Embed and store all chunks, then record the document. Returns the chunk count."""
        chunks = chunk_document(document, self._settings)
        vectors = self._embedder.embed_passages([text_for_embedding(c) for c in chunks])
        # Write the new chunks first (overwriting same positions), THEN trim leftovers from a
        # longer old version: the document never disappears from search in between.
        self._store.upsert_chunks(str(doc_id), chunks, vectors)
        self._store.delete_chunks_from(str(doc_id), first_index=len(chunks))
        self._registry.save(
            doc_id=doc_id,
            source=document.source,
            file_type=document.file_type,
            content_hash=document.content_hash,
            size_bytes=document.size_bytes,
            page_count=document.page_count,
            chunk_count=len(chunks),
        )
        return len(chunks)


@contextmanager
def open_pipeline(settings: Settings) -> Iterator[IngestionPipeline]:
    """Build a ready-to-use pipeline (models loaded, collection and tables created), and
    close its connections afterwards."""
    embedder = Embedder(settings)
    store = VectorStore.from_settings(settings, embedder.dense_size)
    pool = create_pool(settings)
    try:
        store.ensure_collection()
        apply_schema(pool)
        yield IngestionPipeline(settings, embedder, store, DocumentRegistry(pool))
    finally:
        pool.close()
        store.close()
