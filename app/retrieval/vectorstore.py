"""Store and manage chunk vectors in Qdrant.

One **collection** (like a table) holds every chunk as a **point**:
- two *named vectors*: `dense` (meaning, compared by cosine similarity) and `bm25` (keywords;
  Qdrant applies IDF, so rare words like "E-207" weigh more than common ones like "the"),
- a *payload* (the chunk text plus metadata) that is returned with search results and used
  for citations and filters.

Point IDs are computed from (document id, chunk position), so writing the same chunk twice
overwrites it instead of duplicating it. That makes re-running an interrupted ingestion safe.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from qdrant_client import QdrantClient, models

from app.config import Settings
from app.ingestion.models import Chunk
from app.retrieval.embeddings import EmbeddedTexts, SparseVector

log = structlog.get_logger(__name__)

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"
UPSERT_BATCH = 256  # points per request: keeps each HTTP request small
# Fields we filter on get an index, like a database index: fast lookups instead of full scans.
INDEXED_FIELDS = {
    "doc_id": models.PayloadSchemaType.KEYWORD,
    "source": models.PayloadSchemaType.KEYWORD,
    "file_type": models.PayloadSchemaType.KEYWORD,
    "chunk_index": models.PayloadSchemaType.INTEGER,  # range filter when trimming old chunks
}
# Fixed namespace so the same (document, position) always produces the same point ID.
_POINT_NAMESPACE = uuid.UUID("6f1d2c4e-8a3b-4f5e-9c7d-1b2a3c4d5e6f")


SearchMode = Literal["dense", "sparse", "hybrid"]


@dataclass(frozen=True)
class SearchHit:
    """One search result straight from Qdrant: point id, score and stored payload."""

    id: str
    score: float
    payload: dict[str, Any]


class CollectionMismatchError(RuntimeError):
    """The existing collection was built for a different embedding model size."""


def point_id(doc_id: str, chunk_index: int) -> str:
    """Deterministic point ID for one chunk of one document."""
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{doc_id}:{chunk_index}"))


class VectorStore:
    """Thin, well-named wrapper around the Qdrant client for our one collection."""

    def __init__(self, client: QdrantClient, collection: str, dense_size: int) -> None:
        self._client = client
        self.collection = collection
        self._dense_size = dense_size

    @classmethod
    def from_settings(cls, settings: Settings, dense_size: int) -> "VectorStore":
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        client = QdrantClient(
            url=settings.qdrant_url, api_key=api_key, timeout=int(settings.qdrant_timeout_s)
        )
        return cls(client, settings.qdrant_collection, dense_size)

    def ensure_collection(self) -> None:
        """Create the collection (and payload indexes) if it doesn't exist yet."""
        if self._client.collection_exists(self.collection):
            self._check_dense_size()
            return
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=self._dense_size, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        for field, schema in INDEXED_FIELDS.items():
            self._client.create_payload_index(
                self.collection, field_name=field, field_schema=schema
            )
        log.info("collection_created", collection=self.collection, dense_size=self._dense_size)

    def upsert_chunks(self, doc_id: str, chunks: Sequence[Chunk], vectors: EmbeddedTexts) -> int:
        """Write (or overwrite) one document's chunks. Returns the number of points written."""
        points = [
            models.PointStruct(
                id=point_id(doc_id, chunk.chunk_index),
                vector={
                    DENSE_VECTOR: dense,
                    SPARSE_VECTOR: models.SparseVector(
                        indices=sparse.indices, values=sparse.values
                    ),
                },
                payload=_payload(doc_id, chunk),
            )
            for chunk, dense, sparse in zip(chunks, vectors.dense, vectors.sparse, strict=True)
        ]
        for start in range(0, len(points), UPSERT_BATCH):
            batch = points[start : start + UPSERT_BATCH]
            # wait=True: return only once Qdrant has stored the points, so a following
            # search or count already sees them.
            self._client.upsert(self.collection, points=batch, wait=True)
        return len(points)

    def delete_document(self, doc_id: str) -> None:
        """Remove every chunk of one document (used before re-indexing a changed file)."""
        self._client.delete(
            self.collection,
            points_selector=models.FilterSelector(filter=_doc_filter(doc_id)),
            wait=True,
        )

    def delete_chunks_from(self, doc_id: str, first_index: int) -> None:
        """Remove a document's chunks at positions >= first_index.

        After re-indexing a changed file that now has fewer chunks, the old extra chunks
        (with higher positions) would otherwise linger and show up in search results.
        """
        stale = models.Filter(
            must=[
                models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
                models.FieldCondition(key="chunk_index", range=models.Range(gte=first_index)),
            ]
        )
        self._client.delete(
            self.collection, points_selector=models.FilterSelector(filter=stale), wait=True
        )

    def search(
        self,
        dense: list[float],
        sparse: SparseVector,
        *,
        mode: SearchMode = "hybrid",
        limit: int,
        sources: Sequence[str] | None = None,
    ) -> list[SearchHit]:
        """Find the `limit` best chunks for a query.

        - "dense": nearest by meaning (cosine similarity of dense vectors).
        - "sparse": best keyword matches (BM25 with IDF).
        - "hybrid": run both, then merge the two ranked lists with Reciprocal Rank Fusion
          (RRF) inside Qdrant. RRF uses positions, not raw scores, because cosine scores and
          BM25 scores are on different scales and can't be compared directly.
        """
        query_filter = _sources_filter(sources)
        sparse_query = models.SparseVector(indices=sparse.indices, values=sparse.values)
        if mode == "dense":
            kwargs: dict[str, object] = {"query": dense, "using": DENSE_VECTOR}
        elif mode == "sparse":
            kwargs = {"query": sparse_query, "using": SPARSE_VECTOR}
        else:
            kwargs = {
                "prefetch": [
                    models.Prefetch(
                        query=dense, using=DENSE_VECTOR, limit=limit, filter=query_filter
                    ),
                    models.Prefetch(
                        query=sparse_query, using=SPARSE_VECTOR, limit=limit, filter=query_filter
                    ),
                ],
                "query": models.FusionQuery(fusion=models.Fusion.RRF),
            }
        response = self._client.query_points(
            self.collection, query_filter=query_filter, limit=limit, with_payload=True, **kwargs
        )
        return [SearchHit(str(p.id), p.score, p.payload or {}) for p in response.points]

    def count(self, doc_id: str | None = None) -> int:
        """Number of stored chunks, optionally for one document only."""
        query_filter = _doc_filter(doc_id) if doc_id else None
        return self._client.count(self.collection, count_filter=query_filter, exact=True).count

    def drop_collection(self) -> None:
        """Delete the whole collection (tests use this to clean up)."""
        self._client.delete_collection(self.collection)

    def close(self) -> None:
        self._client.close()

    def _check_dense_size(self) -> None:
        info = self._client.get_collection(self.collection)
        vectors = info.config.params.vectors
        existing = vectors[DENSE_VECTOR].size if isinstance(vectors, dict) else None
        if existing != self._dense_size:
            raise CollectionMismatchError(
                f"collection '{self.collection}' stores {existing}-dim vectors but the embedding "
                f"model produces {self._dense_size}; use a new QDRANT_COLLECTION or re-create it"
            )


def _payload(doc_id: str, chunk: Chunk) -> dict[str, object]:
    return {
        "doc_id": doc_id,
        "doc_hash": chunk.doc_hash,
        "source": chunk.source,
        "file_type": chunk.file_type,
        "section": chunk.section,
        "page": chunk.page,
        "chunk_index": chunk.chunk_index,
        "token_count": chunk.token_count,
        "content_hash": chunk.content_hash,
        "text": chunk.text,  # the original chunk text, shown in answers and citations
    }


def _sources_filter(sources: Sequence[str] | None) -> models.Filter | None:
    """Restrict a search to some documents (None or empty = search everything)."""
    if not sources:
        return None
    return models.Filter(
        must=[models.FieldCondition(key="source", match=models.MatchAny(any=list(sources)))]
    )


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
    )
