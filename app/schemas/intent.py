"""Intent classification schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from app.schemas.base import CamelizedBaseStruct

__all__ = (
    "IntentClassification",
    "IntentExemplar",
    "IntentExemplarCreate",
    "IntentExemplarUpdate",
    "IntentResult",
    "IntentSearchResult",
    "IntentStats",
)


class IntentExemplar(CamelizedBaseStruct, omit_defaults=True):
    """Schema for intent exemplar records."""

    id: int
    intent: str
    phrase: str
    embedding: list[float]
    confidence_threshold: float
    usage_count: int
    created_at: datetime
    updated_at: datetime


class IntentResult(CamelizedBaseStruct, omit_defaults=True):
    """Result of intent classification."""

    intent: str
    confidence: float
    exemplar_phrase: str
    embedding_cache_hit: bool
    fallback_used: bool = False


class IntentClassification(CamelizedBaseStruct, omit_defaults=True, kw_only=True):
    """Schema for storing intent classification in chat conversations."""

    intent: str
    confidence: float
    threshold_used: float
    exemplar_match: str | None = None
    processing_time_ms: int | None = None


class IntentExemplarCreate(CamelizedBaseStruct, omit_defaults=True):
    """Schema for creating intent exemplars."""

    intent: str
    phrase: str
    embedding: list[float]
    confidence_threshold: float = 0.7


class IntentExemplarUpdate(CamelizedBaseStruct, omit_defaults=True):
    """Schema for updating intent exemplars."""

    phrase: str | None = None
    embedding: list[float] | None = None
    confidence_threshold: float | None = None


class IntentSearchResult(CamelizedBaseStruct, omit_defaults=True):
    """Schema for intent similarity search results."""

    intent: str
    phrase: str
    similarity: float
    confidence_threshold: float
    usage_count: int = 0


class IntentStats(CamelizedBaseStruct, omit_defaults=True):
    """Schema for intent classification statistics."""

    total_exemplars: int
    intents_count: int
    average_usage: float
    top_intents: list[dict[str, Any]]
    cache_hit_rate: float | None = None
