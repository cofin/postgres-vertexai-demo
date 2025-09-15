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
        metric_id = await self.driver.select_value(
            sql.insert("search_metrics")
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
            .returning("id")
        )

        return await self.get_search_metric(metric_id)

    async def get_search_metric(self, metric_id: UUID) -> SearchMetrics:
        """Get a search metric by ID.

        Args:
            metric_id: Metric UUID

        Returns:
            Search metric data

        Raises:
            ValueError: If metric not found
        """
        return await self.get_or_404(
            sql.select(
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
            )
            .from_("search_metrics")
            .where_eq("id", metric_id),
            schema_type=SearchMetrics,
            error_message=f"Search metric {metric_id} not found",
        )

    async def get_session_metrics(self, session_id: UUID, limit: int = 50) -> list[SearchMetrics]:
        """Get metrics for a specific session.

        Args:
            session_id: Session UUID
            limit: Maximum number of metrics

        Returns:
            List of search metrics for the session
        """
        return await self.driver.select(
            sql.select(
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
            )
            .from_("search_metrics")
            .where_eq("session_id", session_id)
            .order_by("created_at DESC")
            .limit(limit),
            schema_type=SearchMetrics,
        )

    async def get_metrics_summary(self, hours_back: int = 24) -> dict[str, Any]:
        """Get metrics summary for the last N hours.

        Args:
            hours_back: Number of hours to look back

        Returns:
            Dictionary with metrics summary
        """
        summary = await self.driver.select_one_or_none(
            """
            SELECT
              date (created_at) as date,
              count(*) as total_queries,
              count(DISTINCT session_id) as unique_sessions,
              avg(total_response_time_ms) as avg_response_time_ms,
              avg(confidence_score) as avg_confidence_score,
              count(
                CASE
                  WHEN confidence_score < 0.7 THEN 1
                END
              ) as low_confidence_queries
            FROM
              search_metrics
            WHERE
              created_at >= current_timestamp - :hours_back * interval '1 hour'
            GROUP BY
              date (created_at)
            ORDER BY
              date DESC
            """,
            hours_back=hours_back,
        )

        return summary or {
            "total_searches": 0,
            "avg_response_time_ms": 0.0,
            "avg_results_count": 0.0,
            "top_intents": [],
            "search_volume_by_hour": [],
        }

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
              search_metrics
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

    async def get_intent_distribution(self, hours_back: int = 24) -> list[dict[str, Any]]:
        """Get intent distribution for the last N hours.

        Args:
            hours_back: Number of hours to look back

        Returns:
            List of intent counts and percentages
        """
        return await self.driver.select(
            """
            SELECT
              intent,
              count(*) as query_count,
              avg(confidence_score) as avg_confidence,
              avg(total_response_time_ms) as avg_response_time_ms
            FROM
              search_metrics
            WHERE
              created_at >= current_timestamp - :hours_back * interval '1 hour'
              AND intent IS NOT NULL
            GROUP BY
              intent
            ORDER BY
              query_count DESC
            """,
            hours_back=hours_back,
        )

    async def get_search_trends(
        self,
        hours_back: int = 168,  # 1 week
    ) -> list[dict[str, Any]]:
        """Get search trends over time.

        Args:
            hours_back: Number of hours to look back (default: 1 week)

        Returns:
            List of hourly search counts and metrics
        """
        return await self.driver.select(
            """
            SELECT
              extract(
                HOUR
                FROM
                  created_at
              ) as hour,
              count(*) as total_queries,
              count(DISTINCT session_id) as unique_sessions,
              avg(total_response_time_ms) as avg_response_time_ms,
              avg(confidence_score) as avg_confidence_score
            FROM
              search_metrics
            WHERE
              created_at >= current_timestamp - :hours_back * interval '1 hour'
            GROUP BY
              extract(
                HOUR
                FROM
                  created_at
              )
            ORDER BY
              hour
            """,
            hours_back=hours_back,
        )

    async def cleanup_old_metrics(self, days_old: int = 90) -> int:
        """Clean up old search metrics.

        Args:
            days_old: Metrics older than this many days will be deleted

        Returns:
            Number of metrics deleted
        """
        result = await self.driver.execute(
            """
            DELETE FROM search_metrics
            WHERE
              created_at < current_timestamp - :retention_days * interval '1 day'
            """,
            retention_days=days_old,
        )
        return result.get_affected_count()

    async def get_top_queries(self, hours_back: int = 24, limit: int = 10) -> list[dict[str, Any]]:
        """Get top search queries by frequency.

        Args:
            hours_back: Number of hours to look back
            limit: Maximum number of queries to return

        Returns:
            List of top queries with counts
        """
        return await self.driver.select(
            """
            SELECT
              query_text,
              count(*) as query_frequency,
              avg(confidence_score) as avg_confidence,
              avg(total_response_time_ms) as avg_response_time,
              count(DISTINCT session_id) as unique_sessions,
              max(created_at) as last_seen
            FROM
              search_metrics
            WHERE
              created_at >= current_timestamp - :days_back * interval '1 day'
              AND query_text IS NOT NULL
            GROUP BY
              query_text
            HAVING
              count(*) >= :min_frequency
            ORDER BY
              query_frequency DESC
            LIMIT
              :limit_count
            """,
            days_back=hours_back // 24,
            min_frequency=1,
            limit_count=limit,
        )

    async def get_slow_queries(
        self, min_response_time_ms: int = 1000, hours_back: int = 24, limit: int = 20
    ) -> list[SearchMetrics]:
        """Get slow queries above a threshold.

        Args:
            min_response_time_ms: Minimum response time to include
            hours_back: Number of hours to look back
            limit: Maximum number of queries to return

        Returns:
            List of slow search metrics
        """
        return await self.driver.select(
            """
            SELECT
              id,
              session_id,
              query_text,
              intent,
              confidence_score,
              vector_search_time_ms,
              llm_response_time_ms,
              total_response_time_ms,
              created_at
            FROM
              search_metrics
            WHERE
              total_response_time_ms > :response_time_threshold_ms
              AND created_at >= current_timestamp - :hours_back * interval '1 hour'
            ORDER BY
              total_response_time_ms DESC
            LIMIT
              :limit_count
            """,
            response_time_threshold_ms=min_response_time_ms,
            hours_back=hours_back,
            limit_count=limit,
            schema_type=SearchMetrics,
        )
