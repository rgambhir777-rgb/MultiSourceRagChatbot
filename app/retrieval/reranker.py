"""Re-score search results with a cross-encoder.

Vector search is a *bi-encoder*: the question and each chunk are turned into vectors
separately, and compared afterwards. That is fast, but the model never reads them together.

A *cross-encoder* reads the question and one chunk **together** and outputs a relevance score.
It is much more accurate, but too slow to run over every chunk, so we only run it over the
~20 candidates that hybrid search returns, then keep the best few.
"""

import time
from collections.abc import Sequence

import structlog
from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import Settings

log = structlog.get_logger(__name__)


class Reranker:
    """Loads the cross-encoder once and scores (query, passage) pairs."""

    def __init__(self, settings: Settings) -> None:
        started = time.perf_counter()
        self._batch_size = settings.embed_batch_size
        self._model = TextCrossEncoder(
            settings.rerank_model, cache_dir=settings.fastembed_cache_dir
        )
        log.info(
            "reranker_loaded",
            model=settings.rerank_model,
            seconds=round(time.perf_counter() - started, 2),
        )

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """One relevance score per passage (higher = more relevant; not a probability)."""
        if not passages:
            return []
        return [float(s) for s in self._model.rerank(query, passages, batch_size=self._batch_size)]
