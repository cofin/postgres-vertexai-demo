"""PostgreSQL native vector similarity search for intent routing."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from app.schemas import IntentResult
from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from app.services.exemplar import ExemplarService
    from app.services.vertex_ai import VertexAIService

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
        vertex_ai_service: VertexAIService,
    ) -> None:
        """Initialize intent service.

        Args:
            driver: Database driver
            exemplar_service: Service for managing intent exemplars
            vertex_ai_service: Service for generating embeddings
        """
        super().__init__(driver)
        self.exemplar_service = exemplar_service
        self.vertex_ai_service = vertex_ai_service

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
        if user_embedding is None:
            user_embedding, embedding_cache_hit = await self.vertex_ai_service.get_text_embedding_with_cache_status(
                query
            )
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

            logger.debug(
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
