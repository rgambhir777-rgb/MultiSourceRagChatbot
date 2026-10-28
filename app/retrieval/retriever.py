"""`Retriever.retrieve(question)`: the full search funnel.

    question ──embed──► hybrid search (dense + BM25, fused with RRF) ──► ~20 candidates
             ──cross-encoder rerank──► best 5 chunks, each with its source, section and page

Wide-then-narrow: the cheap search casts a wide net so the right chunk is very likely among
the candidates; the expensive reranker then puts the best ones on top.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace

import structlog

from app.config import Settings
from app.ingestion.models import with_context
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vectorstore import SearchHit, SearchMode, VectorStore

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned by retrieval, with everything needed to quote and cite it."""

    id: str
    doc_id: str
    source: str
    section: str
    page: int | None
    chunk_index: int
    text: str
    search_score: float  # from Qdrant (cosine, BM25 or RRF, depending on the mode)
    rerank_score: float | None = None  # from the cross-encoder, when reranking ran

    @property
    def citation(self) -> str:
        """Human-readable location, e.g. "orbit_troubleshooting.pdf, page 1"."""
        parts = [self.source]
        if self.page is not None:
            parts.append(f"page {self.page}")
        if self.section:
            parts.append(self.section)
        return ", ".join(parts)


class Retriever:
    """Embeds the question, searches Qdrant and (optionally) reranks the candidates."""

    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        store: VectorStore,
        reranker: Reranker | None,
    ) -> None:
        self._settings = settings
        self._embedder = embedder
        self._store = store
        self._reranker = reranker

    def retrieve(
        self,
        question: str,
        *,
        mode: SearchMode = "hybrid",
        rerank: bool = True,
        top_k: int | None = None,
        sources: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Return the best chunks for a question, best first."""
        question = question.strip()
        if not question:
            return []
        top_k = top_k or self._settings.rerank_top_k
        started = time.perf_counter()

        dense, sparse = self._embedder.embed_query(question)
        limit = self._settings.retrieve_candidates if rerank else top_k
        hits = self._store.search(dense, sparse, mode=mode, limit=limit, sources=sources)
        chunks = [_to_chunk(hit) for hit in hits]
        searched = time.perf_counter()

        if rerank and self._reranker is not None and chunks:
            chunks = _rerank(self._reranker, question, chunks)
        log.info(
            "retrieval_done",
            mode=mode,
            reranked=rerank and self._reranker is not None,
            candidates=len(hits),
            search_ms=round((searched - started) * 1000, 1),
            rerank_ms=round((time.perf_counter() - searched) * 1000, 1),
        )
        return chunks[:top_k]


def _rerank(
    reranker: Reranker, question: str, chunks: list[RetrievedChunk]
) -> list[RetrievedChunk]:
    """Score every candidate together with the question and sort best-first."""
    passages = [with_context(c.source, c.section, c.text) for c in chunks]
    scores = reranker.score(question, passages)
    scored = [replace(c, rerank_score=s) for c, s in zip(chunks, scores, strict=True)]
    return sorted(scored, key=lambda c: c.rerank_score or 0.0, reverse=True)


def _to_chunk(hit: SearchHit) -> RetrievedChunk:
    payload = hit.payload
    return RetrievedChunk(
        id=hit.id,
        doc_id=str(payload.get("doc_id", "")),
        source=str(payload.get("source", "")),
        section=str(payload.get("section", "")),
        page=payload.get("page"),
        chunk_index=int(payload.get("chunk_index", 0)),
        text=str(payload.get("text", "")),
        search_score=hit.score,
    )
