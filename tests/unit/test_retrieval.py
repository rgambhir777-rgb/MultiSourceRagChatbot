"""Tests for retrieval metrics and the Retriever's funnel logic (fakes, no models/Qdrant)."""

from collections.abc import Sequence

import pytest

from app.config import Settings
from app.retrieval.embeddings import SparseVector
from app.retrieval.retriever import RetrievedChunk, Retriever
from app.retrieval.vectorstore import SearchHit
from evals.metrics import first_correct_rank, hit_at_k, mean_reciprocal_rank
from evals.retrieval_eval import load_golden

# ---------------------------------------------------------------- metrics


def test_hit_at_k_counts_ranks_within_k() -> None:
    ranks = [1, 2, None, 5]
    assert hit_at_k(ranks, 1) == 0.25
    assert hit_at_k(ranks, 2) == 0.5
    assert hit_at_k(ranks, 5) == 0.75
    assert hit_at_k([], 3) == 0.0


def test_mrr_rewards_higher_positions() -> None:
    assert mean_reciprocal_rank([1, 1]) == 1.0
    assert mean_reciprocal_rank([1, 2, None, 4]) == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)


def test_first_correct_rank_needs_source_and_phrase() -> None:
    results = [("a.md", "nothing here"), ("b.md", "Error E-207 explained"), ("a.md", "E-207")]
    assert first_correct_rank(results, "a.md", "e-207") == 3  # case-insensitive phrase
    assert first_correct_rank(results, "c.md", "E-207") is None


def test_golden_set_is_well_formed() -> None:
    golden = load_golden()
    assert len(golden) >= 15
    assert len({g["id"] for g in golden}) == len(golden)
    assert all(g["question"] and g["expected_source"] and g["expected_phrase"] for g in golden)


# ---------------------------------------------------------------- retriever


class FakeEmbedder:
    def embed_query(self, text: str) -> tuple[list[float], SparseVector]:
        return [0.1], SparseVector([1], [1.0])


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def search(self, dense, sparse, *, mode, limit, sources=None) -> list[SearchHit]:  # noqa: ANN001
        self.calls.append({"mode": mode, "limit": limit, "sources": sources})
        return [
            SearchHit(
                id=f"p{i}",
                score=1.0 / (i + 1),
                payload={
                    "doc_id": "d",
                    "source": "s.md",
                    "section": "",
                    "page": None,
                    "chunk_index": i,
                    "text": f"chunk {i}",
                },
            )
            for i in range(limit)
        ]


class FakeReranker:
    """Scores 'chunk 3' highest, to prove the reranker's order wins over search order."""

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        return [10.0 if passage.endswith("chunk 3") else 0.0 for passage in passages]


@pytest.fixture
def retriever_parts(settings: Settings) -> tuple[Retriever, FakeStore]:
    store = FakeStore()
    tuned = settings.model_copy(update={"retrieve_candidates": 8, "rerank_top_k": 3})
    return Retriever(tuned, FakeEmbedder(), store, FakeReranker()), store  # type: ignore[arg-type]


def test_rerank_fetches_candidates_then_reorders(retriever_parts) -> None:
    retriever, store = retriever_parts
    chunks = retriever.retrieve("question")
    assert store.calls[0]["limit"] == 8, "wide net: retrieve_candidates"
    assert len(chunks) == 3, "narrow: rerank_top_k"
    assert chunks[0].text == "chunk 3" and chunks[0].rerank_score == 10.0


def test_without_rerank_search_order_is_kept(retriever_parts) -> None:
    retriever, store = retriever_parts
    chunks = retriever.retrieve("question", rerank=False, mode="dense", top_k=2)
    assert store.calls[0] == {"mode": "dense", "limit": 2, "sources": None}
    assert [c.text for c in chunks] == ["chunk 0", "chunk 1"]
    assert chunks[0].rerank_score is None


def test_blank_question_returns_nothing(retriever_parts) -> None:
    retriever, store = retriever_parts
    assert retriever.retrieve("   ") == []
    assert store.calls == []


def test_source_filter_is_passed_through(retriever_parts) -> None:
    retriever, store = retriever_parts
    retriever.retrieve("question", sources=["a.pdf"])
    assert store.calls[0]["sources"] == ["a.pdf"]


def test_citation_includes_page_and_section() -> None:
    chunk = RetrievedChunk(
        id="1",
        doc_id="d",
        source="guide.pdf",
        section="Setup > Wi-Fi",
        page=2,
        chunk_index=0,
        text="t",
        search_score=1.0,
    )
    assert chunk.citation == "guide.pdf, page 2, Setup > Wi-Fi"
