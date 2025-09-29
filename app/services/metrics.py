"""Metrics service for tracking search and performance metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
        avg_similarity_score: float | None = None,
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
            avg_similarity_score: Average similarity score for vector search results

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
                "avg_similarity_score",
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
                avg_similarity_score=avg_similarity_score,
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
                "avg_similarity_score",
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
              avg(avg_similarity_score) as avg_similarity_score,
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

        if metrics:
            # Map database column names to expected response keys
            return {
                "total_searches": metrics.get("total_queries", 0),
                "avg_search_time_ms": metrics.get("avg_total_response_time_ms", 0.0),
                "avg_similarity_score": metrics.get("avg_similarity_score", 0.0) or 0.0,
                "avg_response_time_ms": metrics.get("avg_total_response_time_ms", 0.0),
                "avg_vector_search_time_ms": metrics.get("avg_vector_search_time_ms", 0.0),
                "avg_llm_response_time_ms": metrics.get("avg_llm_response_time_ms", 0.0),
                "p50_response_time_ms": metrics.get("median_response_time_ms", 0.0),
                "p95_response_time_ms": metrics.get("p95_response_time_ms", 0.0),
                "p99_response_time_ms": metrics.get("p99_response_time_ms", 0.0),
                "min_response_time_ms": metrics.get("min_response_time_ms", 0.0),
                "max_response_time_ms": metrics.get("max_response_time_ms", 0.0),
                "error_rate": await self._calculate_error_rate(hours_back),
            }

        return {
            "total_searches": 0,
            "avg_search_time_ms": 0.0,
            "avg_similarity_score": 0.0,
            "avg_response_time_ms": 0.0,
            "avg_vector_search_time_ms": 0.0,
            "avg_llm_response_time_ms": 0.0,
            "p50_response_time_ms": 0.0,
            "p95_response_time_ms": 0.0,
            "p99_response_time_ms": 0.0,
            "min_response_time_ms": 0.0,
            "max_response_time_ms": 0.0,
            "error_rate": 0.0,
        }

    async def get_time_series_data(self, minutes: int = 60) -> dict[str, Any]:
        """Get time-series performance data for charts.

        Args:
            minutes: Number of minutes to look back

        Returns:
            Dictionary with time series data for charts
        """
        since_time = datetime.now(UTC) - timedelta(minutes=minutes)

        # Get data grouped by 5-minute intervals
        data = await self.driver.select_all(
            """
            SELECT
                TO_CHAR(date_trunc('minute', created_at), 'HH24:MI') as time_bucket,
                AVG(total_response_time_ms) as avg_total,
                AVG(vector_search_time_ms) as avg_postgres,
                AVG(llm_response_time_ms) as avg_llm,
                COUNT(*) as request_count
            FROM search_metric
            WHERE created_at > :since_time
            GROUP BY date_trunc('minute', created_at)
            ORDER BY date_trunc('minute', created_at)
            """,
            since_time=since_time,
        )

        labels = []
        total_latency = []
        postgres_latency = []
        llm_latency = []

        for row in data:
            labels.append(row.get("time_bucket"))
            total_latency.append(round(row.get("avg_total", 0) or 0, 2))
            postgres_latency.append(round(row.get("avg_postgres", 0) or 0, 2))
            llm_latency.append(round(row.get("avg_llm", 0) or 0, 2))

        return {
            "labels": labels,
            "total_latency": total_latency,
            "postgres_latency": postgres_latency,
            "llm_latency": llm_latency,
        }

    async def get_scatter_data(self, hours: int = 1) -> list[dict[str, float]]:
        """Get similarity score vs response time for scatter plot.

        Args:
            hours: Number of hours to look back

        Returns:
            List of scatter plot data points
        """
        since_time = datetime.now(UTC) - timedelta(hours=hours)

        data = await self.driver.select(
            """
            SELECT
                avg_similarity_score,
                vector_search_time_ms,
                total_response_time_ms
            FROM search_metric
            WHERE created_at > :since_time
            AND avg_similarity_score IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 500
            """,
            since_time=since_time,
        )

        return [
            {
                "x": round(row.get("avg_similarity_score", 0) or 0, 3),
                "y": round(row.get("vector_search_time_ms", 0) or 0, 2),
                "total": round(row.get("total_response_time_ms", 0) or 0, 2),
            }
            for row in data
        ]

    async def get_performance_breakdown(self) -> dict[str, Any]:
        """Get average time breakdown for doughnut chart.

        Returns:
            Dictionary with performance breakdown data
        """
        stats = await self.get_performance_metrics(hours=1)

        # Get the averages
        avg_total = stats["avg_response_time_ms"]
        avg_postgres = stats.get("avg_vector_search_time_ms", 0) or 0
        avg_llm = stats.get("avg_llm_response_time_ms", 0) or 0

        # Estimate embedding generation time (typically small, ~10-50ms)
        embedding_time_estimate = min(avg_total * 0.1, 50)

        # Calculate remaining time for app logic
        remaining_time = max(0, avg_total - avg_postgres - avg_llm - embedding_time_estimate)

        return {
            "labels": ["Embedding Generation", "Vector Search", "AI Processing", "Other"],
            "data": [
                round(embedding_time_estimate, 1),
                round(avg_postgres, 1),
                round(avg_llm, 1),
                round(remaining_time, 1),
            ],
        }

    async def get_cache_hit_rate(self, hours_back: int = 24) -> float:
        """Get cache hit rate percentage for the last N hours.

        Args:
            hours_back: Number of hours to look back

        Returns:
            Cache hit rate as percentage (0-100)
        """
        result = await self.driver.select_one_or_none(
            """
            SELECT
                COUNT(*) as total_searches,
                COUNT(*) FILTER (WHERE embedding_cache_hit = true) as cache_hits
            FROM search_metric
            WHERE created_at >= current_timestamp - :hours_back * interval '1 hour'
            """,
            hours_back=hours_back,
        )

        if result and result.get("total_searches", 0) > 0:
            cache_hits = result.get("cache_hits", 0)
            total_searches = result.get("total_searches", 0)
            return round((cache_hits / total_searches) * 100, 1)

        return 0.0

    async def get_active_sessions_count(self) -> int:
        """Get count of active sessions (active within last hour).

        Returns:
            Number of active sessions
        """
        count = await self.driver.select_value(
            """
            SELECT COUNT(*)
            FROM chat_session
            WHERE last_activity >= current_timestamp - interval '1 hour'
            AND (expires_at IS NULL OR expires_at > current_timestamp)
            """,
        )
        return count or 0

    async def get_unique_users_count(self, hours_back: int = 24) -> int:
        """Get count of unique users in the last N hours.

        Args:
            hours_back: Number of hours to look back

        Returns:
            Number of unique users
        """
        count = await self.driver.select_value(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM chat_session
            WHERE user_id IS NOT NULL
            AND last_activity >= current_timestamp - :hours_back * interval '1 hour'
            """,
            hours_back=hours_back,
        )
        return count or 0

    async def get_metric_trends(self) -> dict[str, float]:
        """Get hour-over-hour trends for key metrics.

        Returns:
            Dictionary with trend percentages (positive = increase, negative = decrease)
        """
        trends = await self.driver.select_one_or_none(
            """
            WITH hourly_metrics AS (
                SELECT
                    date_trunc('hour', created_at) as hour_bucket,
                    COUNT(*) as search_count,
                    AVG(total_response_time_ms) as avg_response_time,
                    COUNT(*) FILTER (WHERE embedding_cache_hit = true) as cache_hits,
                    COUNT(*) as total_searches
                FROM search_metric
                WHERE created_at >= current_timestamp - interval '2 hours'
                GROUP BY date_trunc('hour', created_at)
                ORDER BY hour_bucket DESC
                LIMIT 2
            ),
            current_hour AS (
                SELECT * FROM hourly_metrics ORDER BY hour_bucket DESC LIMIT 1
            ),
            previous_hour AS (
                SELECT * FROM hourly_metrics ORDER BY hour_bucket ASC LIMIT 1
            )
            SELECT
                current_hour.search_count as current_searches,
                previous_hour.search_count as previous_searches,
                current_hour.avg_response_time as current_response_time,
                previous_hour.avg_response_time as previous_response_time,
                CASE
                    WHEN current_hour.total_searches > 0 THEN
                        (current_hour.cache_hits::float / current_hour.total_searches) * 100
                    ELSE 0
                END as current_cache_rate,
                CASE
                    WHEN previous_hour.total_searches > 0 THEN
                        (previous_hour.cache_hits::float / previous_hour.total_searches) * 100
                    ELSE 0
                END as previous_cache_rate
            FROM current_hour, previous_hour
            """,
        )

        if not trends:
            return {"searches_trend": 0.0, "response_time_trend": 0.0, "cache_trend": 0.0}

        # Calculate percentage changes
        searches_trend = 0.0
        if trends.get("previous_searches", 0) > 0:
            current = trends.get("current_searches", 0)
            previous = trends.get("previous_searches", 0)
            searches_trend = round(((current - previous) / previous) * 100, 1)

        response_time_trend = 0.0
        if trends.get("previous_response_time", 0) > 0:
            current = trends.get("current_response_time", 0) or 0
            previous = trends.get("previous_response_time", 0) or 0
            response_time_trend = round(((current - previous) / previous) * 100, 1)

        cache_trend = 0.0
        if trends.get("previous_cache_rate", 0) > 0:
            current = trends.get("current_cache_rate", 0) or 0
            previous = trends.get("previous_cache_rate", 0) or 0
            cache_trend = round(current - previous, 1)  # Percentage point difference

        return {
            "searches_trend": searches_trend,
            "response_time_trend": response_time_trend,
            "cache_trend": cache_trend,
        }

    async def _calculate_error_rate(self, hours_back: int) -> float:
        """Calculate error rate based on failed searches or low similarity scores.

        Args:
            hours_back: Number of hours to look back

        Returns:
            Error rate as percentage (0-100)
        """
        result = await self.driver.select_one_or_none(
            """
            SELECT
                COUNT(*) as total_searches,
                COUNT(*) FILTER (
                    WHERE avg_similarity_score IS NULL
                    OR avg_similarity_score < 0.3
                    OR vector_search_results = 0
                ) as failed_searches
            FROM search_metric
            WHERE created_at >= current_timestamp - :hours_back * interval '1 hour'
            """,
            hours_back=hours_back,
        )

        if result and result.get("total_searches", 0) > 0:
            failed = result.get("failed_searches", 0)
            total = result.get("total_searches", 0)
            return round((failed / total) * 100, 1)

        return 0.0
