"""Cache-related schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from app.schemas.base import CamelizedBaseStruct

__all__ = (
    "EmbeddingCache",
    "ResponseCache",
)


class ResponseCache(CamelizedBaseStruct, omit_defaults=True):
    """Response cache data schema."""

    id: int  # Changed from UUID to int to match migration (serial primary key)
    cache_key: str
    response_data: dict[str, Any]  # Changed to match database column name
    expires_at: datetime | None = None
    created_at: datetime | None = None


class EmbeddingCache(CamelizedBaseStruct, omit_defaults=True):
    """Embedding cache data schema."""

    id: int  # Changed from UUID to int to match migration (serial primary key)
    text_hash: str
    embedding: list[float]  # Embedding vector as list of floats
    model: str  # This matches the database column name
    hit_count: int = 0
    last_accessed: datetime | None = None
    created_at: datetime | None = None
