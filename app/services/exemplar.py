"""Service for managing intent exemplars for vector-based intent classification."""

from __future__ import annotations

from typing import Any

import structlog
from sqlspec import sql

from app.schemas import (
    IntentExemplar,
    IntentExemplarCreate,
    IntentSearchResult,
    IntentStats,
)
from app.services.base import SQLSpecService

logger = structlog.get_logger()


class ExemplarService(SQLSpecService):
    """Manages intent exemplars for vector-based intent classification.

    Uses SQLSpec patterns for all database operations.
    Provides CRUD operations and bulk loading for intent exemplars.
    """

    async def get_exemplars_by_intent(self, intent: str) -> list[IntentExemplar]:
        """Get all exemplars for a specific intent.

        Args:
            intent: Intent name

        Returns:
            List of intent exemplars
        """

        return await self.driver.select(
            sql.select(
                "id", "intent", "phrase", "embedding", "confidence_threshold", "usage_count", "created_at", "updated_at",
            )
            .from_("intent_exemplar")
            .where_eq("intent", intent)
            .order_by("usage_count DESC"),
            schema_type=IntentExemplar,
        )

    async def upsert_exemplar(self, exemplar_data: IntentExemplarCreate) -> IntentExemplar:
        """Create or update an intent exemplar.

        Args:
            exemplar_data: Intent exemplar data

        Returns:
            Created or updated intent exemplar
        """
        # Get result WITHOUT the embedding field to avoid vector type deserialization issues
        result = await self.driver.select_one(
            sql.insert("intent_exemplar")
            .columns("intent", "phrase", "embedding", "confidence_threshold")
            .values(
                intent=exemplar_data.intent,
                phrase=exemplar_data.phrase,
                embedding=exemplar_data.embedding,
                confidence_threshold=exemplar_data.confidence_threshold,
            )
            .on_conflict("intent", "phrase")
            .do_update(
                embedding=sql.raw("EXCLUDED.embedding"),
                confidence_threshold=sql.raw("EXCLUDED.confidence_threshold"),
                updated_at=sql.raw("CURRENT_TIMESTAMP"),
            )
            .returning(
                "id", "intent", "phrase", "confidence_threshold", "usage_count", "created_at", "updated_at",
                # Note: "embedding" field removed from RETURNING to avoid vector deserialization issue
            ),
        )

        # Manually construct the complete object with the embedding we already have
        return IntentExemplar(
            id=result["id"],
            intent=result["intent"],
            phrase=result["phrase"],
            embedding=exemplar_data.embedding,  # Use the embedding we already have
            confidence_threshold=result["confidence_threshold"],
            usage_count=result["usage_count"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )

    async def delete_exemplar(self, exemplar_id: int) -> None:
        """Delete an intent exemplar.

        Args:
            exemplar_id: Intent exemplar ID
        """

        await self.driver.execute(sql.delete("intent_exemplar").where_eq("id", exemplar_id))

    async def search_similar_intents(
        self,
        query_embedding: list[float],
        min_threshold: float = 0.6,
        limit: int = 10,
        target_intent: str | None = None,
    ) -> list[IntentSearchResult]:
        """Search for similar intent exemplars using vector similarity.

        Args:
            query_embedding: Query embedding vector
            min_threshold: Minimum similarity threshold
            limit: Maximum number of results
            target_intent: Optional specific intent to search within

        Returns:
            List of similar intent exemplars with similarity scores
        """
        logger.debug(
            "search_similar_intents called", target_intent=target_intent, min_threshold=min_threshold, limit=limit,
        )

        if target_intent is not None and target_intent != "":
            logger.debug("Using search-similar-intents-by-intent query")
            return await self.driver.select(
                """
                WITH query_embedding AS (
                        SELECT
                            intent,
                            phrase,
                            1 - (embedding <=> :query_embedding) AS similarity,
                            confidence_threshold,
                            usage_count
                        FROM intent_exemplar
                    )
                SELECT
                    intent,
                    phrase,
                    similarity,
                    confidence_threshold,
                    usage_count
                FROM query_embedding
                WHERE intent = :target_intent
                AND similarity > :min_threshold
                ORDER BY similarity DESC
                LIMIT :limit
                """,
                query_embedding=query_embedding,
                min_threshold=min_threshold,
                target_intent=target_intent,
                limit=limit,
                schema_type=IntentSearchResult,
            )

        logger.debug("Using search-similar-intents query")
        # Try removing schema_type to see if that's the issue
        return await self.driver.select(
            """
            WITH
                query_embedding AS (
                    SELECT
                        intent,
                        phrase,
                        1 - (embedding <=> :query_embedding) AS similarity,
                        confidence_threshold,
                        usage_count
                    FROM
                        intent_exemplar
                )
            SELECT
                intent,
                phrase,
                similarity,
                confidence_threshold,
                usage_count
            FROM
                query_embedding
            WHERE
                similarity > :min_threshold
            ORDER BY
                similarity DESC
            LIMIT
                :limit
            """,
            query_embedding=query_embedding,
            min_threshold=min_threshold,
            limit=limit,
            schema_type=IntentSearchResult,
        )

    async def increment_usage_by_phrase(self, intent: str, phrase: str) -> None:
        """Increment usage count for an exemplar by intent and phrase.

        Args:
            intent: Intent name
            phrase: Exemplar phrase
        """
        await self.driver.execute(
            sql.update("intent_exemplar")
            .set(usage_count=sql.raw("usage_count + 1"))
            .where_eq("intent", intent)
            .where_eq("phrase", phrase),
        )

    async def load_exemplars_bulk(
        self,
        exemplars: dict[str, list[str]],
        embedding_service: Any,  # To avoid circular import
        default_threshold: float = 0.7,
    ) -> int:
        """Load intent exemplars in bulk with embeddings.

        Args:
            exemplars: Dictionary mapping intent -> list of phrases
            embedding_service: Service for generating embeddings
            default_threshold: Default confidence threshold

        Returns:
            Number of exemplars created/updated
        """
        count = 0

        logger.info("Starting bulk exemplar loading", total_intents=len(exemplars))

        for intent, phrases in exemplars.items():
            logger.debug("Loading exemplars for intent", intent=intent, phrase_count=len(phrases))

            # Generate embeddings for all phrases at once
            embeddings = await embedding_service.get_text_embedding(phrases)

            # Create exemplars
            for phrase, embedding in zip(phrases, embeddings, strict=False):
                try:
                    await self.upsert_exemplar(
                        IntentExemplarCreate(
                            intent=intent,
                            phrase=phrase,
                            embedding=embedding,
                            confidence_threshold=default_threshold,
                        ),
                    )
                    count += 1

                    if count % 10 == 0:
                        logger.debug("Loaded exemplars", count=count)

                except Exception as e:
                    logger.exception(
                        "Failed to load exemplar",
                        intent=intent,
                        phrase=phrase[:50],
                        error=str(e),
                    )

        logger.info("Completed bulk exemplar loading", total_loaded=count)
        return count

    async def get_intent_stats(self) -> IntentStats:
        """Get intent classification statistics.

        Returns:
            Intent statistics
        """
        # Get basic stats
        stats = await self.driver.select_one_or_none(
            """
            SELECT
                count(*) as total_exemplars,
                count(DISTINCT intent) as intents_count,
                avg(usage_count) as average_usage
            FROM intent_exemplar
            """,
        )

        if not stats:
            return IntentStats(
                total_exemplars=0,
                intents_count=0,
                average_usage=0.0,
                top_intents=[],
            )

        # Get top intents
        top_intents_raw = await self.driver.select(
            """
            SELECT
                intent,
                count(*) as exemplar_count,
                sum(usage_count) as total_usage,
                avg(confidence_threshold) as avg_threshold
            FROM
                intent_exemplar
            GROUP BY
                intent
            ORDER BY
                total_usage DESC,
                exemplar_count DESC
            LIMIT
                :limit
            """,
            limit=10,
        )

        top_intents = [
            {
                "intent": row["intent"],
                "exemplar_count": int(row["exemplar_count"]),
                "total_usage": int(row["total_usage"]),
                "avg_threshold": float(row["avg_threshold"]),
            }
            for row in top_intents_raw
        ]

        return IntentStats(
            total_exemplars=int(stats["total_exemplars"]),
            intents_count=int(stats["intents_count"]),
            average_usage=float(stats["average_usage"]),
            top_intents=top_intents,
        )

    async def clean_unused_exemplars(self, days_old: int = 90) -> int:
        """Clean up unused intent exemplars.

        Args:
            days_old: Delete exemplars older than this many days with 0 usage

        Returns:
            Number of deleted exemplars
        """
        result = await self.driver.select_value_or_none(
            """
            DELETE FROM intent_exemplar
            WHERE
                usage_count = 0
                AND created_at < now() - interval ':days_old days'
            """,
            days_old=days_old,
        )
        if result is not None:
            logger.info("Cleaned unused exemplars", deleted_count=result)
            return result  # type: ignore[no-any-return]

        return 0
