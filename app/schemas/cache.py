"""Cache-related schemas."""

from datetime import datetime
from typing import Any

import msgspec

__all__ = (
    "EmbeddingCache",
    "ResponseCache",
)


class ResponseCache(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Response cache data schema."""

    id: int
    cache_key: str
    response_data: dict[str, Any]
    expires_at: datetime | None = None
    created_at: datetime | None = None


class EmbeddingCache(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Embedding cache data schema."""

    id: int
    text_hash: str
    embedding: list[float]
    model: str
    hit_count: int = 0
    last_accessed: datetime | None = None
    created_at: datetime | None = None
