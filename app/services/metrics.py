"""Metrics service for tracking search and performance metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import sql

from app.schemas import SearchMetrics
from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from uuid import UUID


class MetricsService(SQLSpecService):
    """Handles database operations for search and performance metrics."""

    async def record_search_metric(
        self,
        session_id: UUID | None,
        query_text: str,
        intent: str | None,
        vector_search_results: int,
        total_response_time_ms: int,
        confidence_score: float | None = None,
        vector_search_time_ms: int | None = None,
        llm_response_time_ms: int | None = None,
        embedding_cache_hit: bool = False,
        intent_exemplar_used: str | None = None,
    ) -> SearchMetrics:
        """Record a search metric.

        Args:
            session_id: Optional session UUID
            query_text: Search query text
            intent: Detected intent
            vector_search_results: Number of vector search results returned
            total_response_time_ms: Total response time in milliseconds
            confidence_score: Confidence score for intent classification
            vector_search_time_ms: Vector search time in milliseconds
            llm_response_time_ms: LLM response time in milliseconds
            embedding_cache_hit: Whether embedding was cached
            intent_exemplar_used: Which intent exemplar was used

        Returns:
            Created search metric
        """
        return await self.driver.select_one(
            sql.insert("search_metric")
            .columns(
                "session_id",
                "query_text",
                "intent",
                "confidence_score",
                "vector_search_results",
                "vector_search_time_ms",
                "llm_response_time_ms",
                "total_response_time_ms",
                "embedding_cache_hit",
                "intent_exemplar_used",
            )
            .values(
                session_id=session_id,
                query_text=query_text,
                intent=intent,
                confidence_score=confidence_score,
                vector_search_results=vector_search_results,
                vector_search_time_ms=vector_search_time_ms,
                llm_response_time_ms=llm_response_time_ms,
                total_response_time_ms=total_response_time_ms,
                embedding_cache_hit=embedding_cache_hit,
                intent_exemplar_used=intent_exemplar_used,
            )
            .returning(
                "id",
                "session_id",
                "query_text",
                "intent",
                "confidence_score",
                "vector_search_results",
                "vector_search_time_ms",
                "llm_response_time_ms",
                "total_response_time_ms",
                "embedding_cache_hit",
                "intent_exemplar_used",
                "created_at",
            ),
            schema_type=SearchMetrics,
        )

    async def get_performance_metrics(self, hours_back: int = 24) -> dict[str, Any]:
        """Get performance metrics for the last N hours.

        Args:
            hours_back: Number of hours to look back

        Returns:
            Dictionary with performance metrics
        """
        metrics = await self.driver.select_one_or_none(
            """
            SELECT
              count(*) as total_queries,
              avg(vector_search_time_ms) as avg_vector_search_time_ms,
              avg(llm_response_time_ms) as avg_llm_response_time_ms,
              avg(total_response_time_ms) as avg_total_response_time_ms,
              percentile_cont(0.50) WITHIN GROUP (
                ORDER BY
                  total_response_time_ms
              ) as median_response_time_ms,
              percentile_cont(0.95) WITHIN GROUP (
                ORDER BY
                  total_response_time_ms
              ) as p95_response_time_ms,
              percentile_cont(0.99) WITHIN GROUP (
                ORDER BY
                  total_response_time_ms
              ) as p99_response_time_ms,
              min(total_response_time_ms) as min_response_time_ms,
              max(total_response_time_ms) as max_response_time_ms
            FROM
              search_metric
            WHERE
              created_at >= current_timestamp - :hours_back * interval '1 hour'
            """,
            hours_back=hours_back,
        )

        return metrics or {
            "avg_response_time_ms": 0.0,
            "p50_response_time_ms": 0.0,
            "p95_response_time_ms": 0.0,
            "p99_response_time_ms": 0.0,
            "total_searches": 0,
            "error_rate": 0.0,
        }





