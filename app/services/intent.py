"""PostgreSQL native vector similarity search for intent routing."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from app.schemas import IntentResult, IntentSearchResult
from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from app.services.embedding import EmbeddingService
    from app.services.exemplar import ExemplarService

logger = structlog.get_logger()


class IntentService(SQLSpecService):
    """PostgreSQL native vector similarity search for intent routing.

    Uses pgvector for efficient similarity search.
    Integrates with embedding cache for performance.
    """

    def __init__(
        self,
        driver: Any,
        exemplar_service: ExemplarService,
        embedding_service: EmbeddingService,
    ) -> None:
        """Initialize intent service.

        Args:
            driver: Database driver
            exemplar_service: Service for managing intent exemplars
            embedding_service: Service for generating embeddings
        """
        super().__init__(driver)
        self.exemplar_service = exemplar_service
        self.embedding_service = embedding_service

    async def classify_intent(
        self,
        query: str,
        user_embedding: list[float] | None = None,
        min_threshold: float = 0.6,
        max_results: int = 5,
    ) -> IntentResult:
        """Classify intent using vector similarity with exemplars.

        Args:
            query: User query text
            user_embedding: Pre-computed embedding (optional)
            min_threshold: Minimum similarity threshold
            max_results: Maximum number of results to consider

        Returns:
            Intent classification result
        """
        start_time = time.perf_counter()

        # Get query embedding
        embedding_cache_hit = False
        if user_embedding is None:
            # This will use the two-tier cache in EmbeddingService
            user_embedding = await self.embedding_service.get_text_embedding(query)
            # Note: EmbeddingService handles cache hit tracking internally
        else:
            embedding_cache_hit = True

        # Search for similar intents
        similar_intents = await self.exemplar_service.search_similar_intents(
            query_embedding=user_embedding,
            min_threshold=min_threshold,
            limit=max_results,
        )

        processing_time = int((time.perf_counter() - start_time) * 1000)

        # Determine best intent
        if not similar_intents:
            logger.debug(
                "No intent match found, using fallback",
                query=query[:100],
                min_threshold=min_threshold,
                processing_time_ms=processing_time,
            )

            return IntentResult(
                intent="GENERAL_CONVERSATION",
                confidence=0.0,
                exemplar_phrase="",
                embedding_cache_hit=embedding_cache_hit,
                fallback_used=True,
            )

        # Get the best match
        best_match = similar_intents[0]

        # Check if it meets the intent-specific confidence threshold
        if best_match.similarity >= best_match.confidence_threshold:
            # Increment usage count for the matched exemplar
            await self.exemplar_service.increment_usage_by_phrase(best_match.intent, best_match.phrase)

            logger.info(
                "Intent classified successfully",
                query=query[:100],
                intent=best_match.intent,
                confidence=best_match.similarity,
                exemplar=best_match.phrase[:50],
                processing_time_ms=processing_time,
            )

            return IntentResult(
                intent=best_match.intent,
                confidence=best_match.similarity,
                exemplar_phrase=best_match.phrase,
                embedding_cache_hit=embedding_cache_hit,
                fallback_used=False,
            )
        logger.debug(
            "Intent match below threshold, using fallback",
            query=query[:100],
            best_intent=best_match.intent,
            similarity=best_match.similarity,
            threshold=best_match.confidence_threshold,
            processing_time_ms=processing_time,
        )

        return IntentResult(
            intent="GENERAL_CONVERSATION",
            confidence=best_match.similarity,
            exemplar_phrase=best_match.phrase,
            embedding_cache_hit=embedding_cache_hit,
            fallback_used=True,
        )

    async def classify_intent_with_alternatives(
        self,
        query: str,
        user_embedding: list[float] | None = None,
        min_threshold: float = 0.6,
        max_results: int = 5,
    ) -> tuple[IntentResult, list[IntentSearchResult]]:
        """Classify intent and return alternatives.

        Args:
            query: User query text
            user_embedding: Pre-computed embedding (optional)
            min_threshold: Minimum similarity threshold
            max_results: Maximum number of results to return

        Returns:
            Tuple of (primary result, alternative matches)
        """
        start_time = time.perf_counter()

        # Get query embedding
        embedding_cache_hit = False
        if user_embedding is None:
            user_embedding = await self.embedding_service.get_text_embedding(query)
        else:
            embedding_cache_hit = True

        # Search for similar intents
        similar_intents = await self.exemplar_service.search_similar_intents(
            query_embedding=user_embedding,
            min_threshold=min_threshold,
            limit=max_results,
        )

        processing_time = int((time.perf_counter() - start_time) * 1000)

        # Determine best intent
        if not similar_intents:
            return (
                IntentResult(
                    intent="GENERAL_CONVERSATION",
                    confidence=0.0,
                    exemplar_phrase="",
                    embedding_cache_hit=embedding_cache_hit,
                    fallback_used=True,
                ),
                [],
            )

        # Get the best match
        best_match = similar_intents[0]

        # Create primary result
        if best_match.similarity >= best_match.confidence_threshold:
            await self.exemplar_service.increment_usage_by_phrase(best_match.intent, best_match.phrase)

            primary_result = IntentResult(
                intent=best_match.intent,
                confidence=best_match.similarity,
                exemplar_phrase=best_match.phrase,
                embedding_cache_hit=embedding_cache_hit,
                fallback_used=False,
            )
        else:
            primary_result = IntentResult(
                intent="GENERAL_CONVERSATION",
                confidence=best_match.similarity,
                exemplar_phrase=best_match.phrase,
                embedding_cache_hit=embedding_cache_hit,
                fallback_used=True,
            )

        logger.info(
            "Intent classified with alternatives",
            query=query[:100],
            primary_intent=primary_result.intent,
            alternatives_count=len(similar_intents) - 1,
            processing_time_ms=processing_time,
        )

        return primary_result, similar_intents

    async def get_intent_confidence(
        self,
        query: str,
        target_intent: str,
        user_embedding: list[float] | None = None,
    ) -> float:
        """Get confidence score for a specific intent.

        Args:
            query: User query text
            target_intent: Intent to check confidence for
            user_embedding: Pre-computed embedding (optional)

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Get query embedding
        if user_embedding is None:
            user_embedding = await self.embedding_service.get_text_embedding(query)

        # Search within specific intent
        similar_intents = await self.exemplar_service.search_similar_intents(
            query_embedding=user_embedding,
            min_threshold=0.0,  # Get all results
            limit=1,
            target_intent=target_intent,
        )

        if similar_intents:
            return similar_intents[0].similarity

        return 0.0

    async def validate_intent_setup(self) -> dict[str, Any]:
        """Validate that intent classification is properly set up.

        Returns:
            Dictionary with validation results
        """
        stats = await self.exemplar_service.get_intent_stats()

        validation_result = {
            "is_ready": stats.total_exemplars > 0,
            "total_exemplars": stats.total_exemplars,
            "intents_count": stats.intents_count,
            "average_usage": stats.average_usage,
            "embedding_service_available": self.embedding_service.is_available(),
            "top_intents": stats.top_intents[:5],
        }

        if validation_result["is_ready"]:
            logger.info("Intent classification is ready", **validation_result)
        else:
            logger.warning("Intent classification not ready", **validation_result)

        return validation_result

    async def retrain_intent(
        self,
        intent: str,
        new_phrases: list[str],
        confidence_threshold: float | None = None,
    ) -> int:
        """Retrain an intent with new exemplar phrases.

        Args:
            intent: Intent name
            new_phrases: New exemplar phrases
            confidence_threshold: Optional new confidence threshold

        Returns:
            Number of new exemplars added
        """
        logger.info(
            "Retraining intent",
            intent=intent,
            new_phrases_count=len(new_phrases),
        )

        # Add new exemplars
        count = await self.exemplar_service.load_exemplars_bulk(
            exemplars={intent: new_phrases},
            embedding_service=self.embedding_service,
            default_threshold=confidence_threshold or 0.7,
        )

        # Update threshold if specified
        if confidence_threshold is not None:
            await self.exemplar_service.update_intent_thresholds(intent, confidence_threshold)

        logger.info(
            "Intent retrained successfully",
            intent=intent,
            new_exemplars=count,
        )

        return count
