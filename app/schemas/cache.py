"""Cache-related schemas."""

from datetime import datetime
from typing import Any

import msgspec

__all__ = (
    "EmbeddingCache",
    "ResponseCache",
    "VectorSearchCache",
)


class ResponseCache(msgspec.Struct, gc=False, omit_defaults=True):
    """Response cache data schema."""

    id: int
    cache_key: str
    response_data: dict[str, Any]
    expires_at: datetime | None = None
    created_at: datetime | None = None


class EmbeddingCache(msgspec.Struct, gc=False, omit_defaults=True):
    """Embedding cache data schema."""

    id: int
    text_hash: str
    embedding: list[float]
    model: str
    hit_count: int = 0
    last_accessed: datetime | None = None
    created_at: datetime | None = None


class VectorSearchCache(msgspec.Struct, gc=False, omit_defaults=True):
    """Vector search result cache schema.

    Caches vector similarity search results to reduce query latency.
    Cache key: hash(embedding[:10] + threshold + limit)
    TTL: 1 minute (products rarely change)
    """

    id: int
    embedding_hash: str
    similarity_threshold: float
    result_limit: int
    product_ids: list[int]
    results_count: int
    expires_at: datetime
    created_at: datetime | None = None
    last_accessed: datetime | None = None
    hit_count: int = 1
