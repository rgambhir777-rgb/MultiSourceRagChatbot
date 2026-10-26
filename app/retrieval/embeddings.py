"""Turn text into vectors with FastEmbed (ONNX models, CPU-only, no PyTorch).

Every chunk gets two vectors:
- **dense** (bge-small, 384 numbers): captures *meaning*, so "set up Wi-Fi" is close to
  "connect to the wireless network" even though they share almost no words.
- **sparse** (BM25): one weight per word that appears, so exact terms like an error code
  "E-207" or a function name match strongly.

Session 4 combines both ("hybrid search"). Documents and queries are embedded with different
methods because both models treat a short question differently from a passage of text.
Models download once into FASTEMBED_CACHE_DIR, then load from disk.
"""

import os
import time
from collections.abc import Sequence
from dataclasses import dataclass

# The model downloader warns that Windows can't create symlinks without Developer Mode; it then
# copies files instead, which works fine. Silence it so it doesn't look like an error.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import structlog  # noqa: E402 - must come after the environment tweak above
from fastembed import SparseTextEmbedding, TextEmbedding  # noqa: E402

from app.config import Settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SparseVector:
    """Word ids and their weights; every word not listed has weight 0."""

    indices: list[int]
    values: list[float]


@dataclass(frozen=True)
class EmbeddedTexts:
    """Dense and sparse vectors for a list of texts, in the same order as the input."""

    dense: list[list[float]]
    sparse: list[SparseVector]


class Embedder:
    """Loads both embedding models once and reuses them for every call (loading is slow)."""

    def __init__(self, settings: Settings) -> None:
        started = time.perf_counter()
        self._batch_size = settings.embed_batch_size
        self._dense = TextEmbedding(
            settings.embed_dense_model, cache_dir=settings.fastembed_cache_dir
        )
        self._sparse = SparseTextEmbedding(
            settings.embed_sparse_model, cache_dir=settings.fastembed_cache_dir
        )
        self.dense_model = settings.embed_dense_model
        self.dense_size = self._dense.embedding_size
        log.info(
            "embedding_models_loaded",
            dense=settings.embed_dense_model,
            sparse=settings.embed_sparse_model,
            dims=self.dense_size,
            seconds=round(time.perf_counter() - started, 2),
        )

    def embed_passages(self, texts: Sequence[str]) -> EmbeddedTexts:
        """Embed document chunks (in batches, to bound memory use)."""
        dense = self._dense.passage_embed(list(texts), batch_size=self._batch_size)
        sparse = self._sparse.passage_embed(list(texts), batch_size=self._batch_size)
        return EmbeddedTexts(
            dense=[vector.tolist() for vector in dense],
            sparse=[SparseVector(s.indices.tolist(), s.values.tolist()) for s in sparse],
        )

    def embed_query(self, text: str) -> tuple[list[float], SparseVector]:
        """Embed one search question (used from Session 4)."""
        dense = next(iter(self._dense.query_embed(text)))
        sparse = next(iter(self._sparse.query_embed(text)))
        return dense.tolist(), SparseVector(sparse.indices.tolist(), sparse.values.tolist())
