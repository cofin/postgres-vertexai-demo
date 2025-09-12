"""Cache-related schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import msgspec

__all__ = (
    "EmbeddingCache",
    "ResponseCache",
)


class ResponseCache(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Response cache data schema."""

    id: int  # Changed from UUID to int to match migration (serial primary key)
    cache_key: str
    response_data: dict[str, Any]  # Changed to match database column name
    expires_at: datetime | None = None
    created_at: datetime | None = None


class EmbeddingCache(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Embedding cache data schema."""

    id: int  # Changed from UUID to int to match migration (serial primary key)
    text_hash: str
    embedding: list[float]  # Changed to match database column name
    model: str  # This matches the database column name
    hit_count: int = 0
    last_accessed: datetime | None = None
    created_at: datetime | None = None
