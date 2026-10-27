"""Hybrid search + reranking against a real (throwaway) Qdrant collection.

Run with:  pytest -m integration
"""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.chunking import chunk_document
from app.ingestion.loaders import load_document
from app.ingestion.pipeline import document_id, text_for_embedding
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.retriever import Retriever
from app.retrieval.vectorstore import VectorStore

pytestmark = pytest.mark.integration

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_docs"


@pytest.fixture(scope="module")
def retriever() -> Iterator[Retriever]:
    settings = Settings(qdrant_collection=f"test_{uuid.uuid4().hex[:10]}")
    embedder = Embedder(settings)
    store = VectorStore.from_settings(settings, embedder.dense_size)
    store.ensure_collection()
    try:
        for path in sorted(SAMPLES.iterdir()):
            chunks = chunk_document(load_document(path, settings), settings)
            vectors = embedder.embed_passages([text_for_embedding(c) for c in chunks])
            store.upsert_chunks(str(document_id(path.name)), chunks, vectors)
        yield Retriever(settings, embedder, store, Reranker(settings))
    finally:
        store.drop_collection()
        store.close()


@pytest.mark.parametrize(
    ("question", "source", "phrase"),
    [
        ("What does error E-207 mean?", "orbit_troubleshooting.pdf", "E-207"),
        (
            "How long until I get my money back after a return?",
            "lumen_warranty_returns.docx",
            "10 business days",
        ),
        (
            "How do I wipe the thermostat back to how it came out of the box?",
            "orbit_faq.txt",
            "Factory reset",
        ),
    ],
)
def test_hybrid_rerank_puts_the_answer_first(
    retriever: Retriever, question: str, source: str, phrase: str
) -> None:
    best = retriever.retrieve(question)[0]
    assert best.source == source
    assert phrase in best.text
    assert best.rerank_score is not None


def test_pdf_results_carry_page_numbers(retriever: Retriever) -> None:
    best = retriever.retrieve("The display is blank, what should I check?")[0]
    assert best.source == "orbit_troubleshooting.pdf"
    assert best.page == 2


def test_source_filter_limits_results(retriever: Retriever) -> None:
    chunks = retriever.retrieve("warranty", sources=["orbit_faq.txt"])
    assert chunks and {c.source for c in chunks} == {"orbit_faq.txt"}
