"""Tests for app.retrieval.embeddings using the real models.

The models download once (~75 MB) into FASTEMBED_CACHE_DIR; after that these tests run offline.
"""

import math

import pytest

from app.config import Settings
from app.retrieval.embeddings import Embedder


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    # Module scope: load the models once for all tests in this file (loading takes seconds).
    return Embedder(Settings(_env_file=None))


def test_dense_vectors_have_the_model_dimension(embedder: Embedder) -> None:
    result = embedder.embed_passages(["one", "two", "three"])
    assert embedder.dense_size == 384
    assert [len(v) for v in result.dense] == [384, 384, 384]
    assert len(result.sparse) == 3


def test_similar_meaning_scores_higher_than_unrelated(embedder: Embedder) -> None:
    question = "How do I connect the thermostat to Wi-Fi?"
    paraphrase = "Steps to join the device to a wireless network."
    unrelated = "The warranty lasts two years from the date of purchase."
    dense = embedder.embed_passages([question, paraphrase, unrelated]).dense
    assert _cosine(dense[0], dense[1]) > _cosine(dense[0], dense[2]) + 0.2


def test_sparse_vectors_contain_only_words_present(embedder: Embedder) -> None:
    sparse = embedder.embed_passages(["thermostat thermostat wifi", "warranty"]).sparse
    assert 0 < len(sparse[0].indices) <= 3
    assert len(sparse[0].indices) == len(sparse[0].values)
    assert not set(sparse[0].indices) & set(sparse[1].indices), "no shared words, no shared ids"


def test_exact_terms_share_sparse_ids_between_query_and_passage(embedder: Embedder) -> None:
    passage = embedder.embed_passages(["Error E-207 means the Wi-Fi connection failed."]).sparse[0]
    _, query = embedder.embed_query("what is E-207")
    assert set(query.indices) & set(passage.indices), "the code E-207 must match by keyword"


def test_embedding_is_deterministic(embedder: Embedder) -> None:
    first = embedder.embed_passages(["same text"])
    second = embedder.embed_passages(["same text"])
    assert first == second


def test_query_embedding_has_both_vectors(embedder: Embedder) -> None:
    dense, sparse = embedder.embed_query("how long is the warranty?")
    assert len(dense) == 384
    assert sparse.indices
