"""Intent classification schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IntentExemplar(BaseModel):
    """Schema for intent exemplar records."""

    id: int
    intent: str
    phrase: str
    embedding: list[float]
    confidence_threshold: float
    usage_count: int
    created_at: datetime
    updated_at: datetime


class IntentResult(BaseModel):
    """Result of intent classification."""

    intent: str
    confidence: float
    exemplar_phrase: str
    embedding_cache_hit: bool
    fallback_used: bool = False


class IntentClassification(BaseModel):
    """Schema for storing intent classification in chat conversations."""

    intent: str
    confidence: float
    exemplar_match: str | None = None
    threshold_used: float
    processing_time_ms: int | None = None


class IntentExemplarCreate(BaseModel):
    """Schema for creating intent exemplars."""

    intent: str
    phrase: str
    embedding: list[float]
    confidence_threshold: float = 0.7


class IntentExemplarUpdate(BaseModel):
    """Schema for updating intent exemplars."""

    phrase: str | None = None
    embedding: list[float] | None = None
    confidence_threshold: float | None = None


class IntentSearchResult(BaseModel):
    """Schema for intent similarity search results."""

    intent: str
    phrase: str
    similarity: float
    confidence_threshold: float
    usage_count: int = 0


class IntentStats(BaseModel):
    """Schema for intent classification statistics."""

    total_exemplars: int
    intents_count: int
    average_usage: float
    top_intents: list[dict[str, Any]]
    cache_hit_rate: float | None = None
