"""The API's shared building blocks, created lazily and closed at shutdown.

Loading models and opening database pools takes time and needs the Docker services, so
nothing is created when the app starts: each piece is built the first time a request needs
it, then reused. This keeps startup instant and lets tests swap in fakes (or never touch
these at all, e.g. the health checks).
"""

import threading
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from psycopg_pool import ConnectionPool

from app.config import Settings
from app.db.jobs import JobStore
from app.db.pool import apply_schema, create_pool
from app.db.repositories import DocumentRegistry
from app.ingestion.jobs import JobRunner
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.embeddings import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.retriever import Retriever
from app.retrieval.vectorstore import VectorStore

log = structlog.get_logger(__name__)
T = TypeVar("T")


class Services:
    """Lazily-built singletons for one app instance. Thread-safe: requests and the ingestion
    worker may ask for the same piece at the same time."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()  # re-entrant: building one piece may build another
        self._built: dict[str, Any] = {}

    def pool(self) -> ConnectionPool:
        def build() -> ConnectionPool:
            pool = create_pool(self.settings)
            apply_schema(pool)
            return pool

        return self._get("pool", build)

    def embedder(self) -> Embedder:
        return self._get("embedder", lambda: Embedder(self.settings))

    def reranker(self) -> Reranker:
        return self._get("reranker", lambda: Reranker(self.settings))

    def store(self) -> VectorStore:
        def build() -> VectorStore:
            store = VectorStore.from_settings(self.settings, self.embedder().dense_size)
            store.ensure_collection()
            return store

        return self._get("store", build)

    def registry(self) -> DocumentRegistry:
        return self._get("registry", lambda: DocumentRegistry(self.pool()))

    def jobs(self) -> JobStore:
        return self._get("jobs", lambda: JobStore(self.pool()))

    def pipeline(self) -> IngestionPipeline:
        return self._get(
            "pipeline",
            lambda: IngestionPipeline(
                self.settings, self.embedder(), self.store(), self.registry()
            ),
        )

    def job_runner(self) -> JobRunner:
        def build() -> JobRunner:
            interrupted = self.jobs().fail_interrupted()
            if interrupted:
                log.warning("interrupted_jobs_marked_failed", count=interrupted)
            return JobRunner(self.jobs(), self.pipeline)

        return self._get("job_runner", build)

    def retriever(self) -> Retriever:
        return self._get(
            "retriever",
            lambda: Retriever(self.settings, self.embedder(), self.store(), self.reranker()),
        )

    def close(self) -> None:
        """Release whatever was actually created (in reverse dependency order)."""
        with self._lock:
            if "job_runner" in self._built:
                self._built["job_runner"].shutdown()
            if "store" in self._built:
                self._built["store"].close()
            if "pool" in self._built:
                self._built["pool"].close()
            self._built.clear()

    def _get(self, name: str, build: Callable[[], T]) -> T:
        with self._lock:
            if name not in self._built:
                self._built[name] = build()
                log.info("service_ready", service=name)
            return self._built[name]
