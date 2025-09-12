"""Metrics-related schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = ("SearchMetrics",)


class SearchMetrics(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Search metrics data schema."""

    id: UUID
    session_id: UUID | None = None
    query_text: str | None = None
    intent: str | None = None
    confidence_score: float | None = None
    vector_search_results: int | None = None
    vector_search_time_ms: int | None = None
    llm_response_time_ms: int | None = None
    total_response_time_ms: int | None = None
    embedding_cache_hit: bool | None = False
    intent_exemplar_used: str | None = None
    created_at: datetime | None = None
