"""Service for managing cached intent exemplar embeddings."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np
import structlog

from cymbal.config import db_manager
from cymbal.services.base import SQLSpecService

if TYPE_CHECKING:
    from sqlspec import AsyncDriverAdapterBase

    from cymbal.services._vertex_ai import VertexAIService

logger = structlog.get_logger()


class ExemplarService(SQLSpecService):
    """Service for managing intent exemplar embeddings using SQLSpec driver patterns."""

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize the service."""
        super().__init__(driver)

    async def get_exemplars_with_phrases(self) -> dict[str, list[tuple[str, list[float]]]]:
        """Get all exemplars with their phrases and embeddings."""
        results = await self.driver.select(db_manager.get_sql("get-exemplars-with-phrases"))

        result: dict[str, list[tuple[str, list[float]]]] = {}
        for row in results:
            # Database returns column names
            intent: str = cast("str", row.get("intent"))
            phrase = cast("str", row.get("phrase"))
            embedding_vector = row.get("embedding")
            if embedding_vector is None:
                embedding_vector = row.get("EMBEDDING")
            if embedding_vector is not None:
                # SQLSpec handles database vector to Python list conversion automatically
                embedding = list(embedding_vector) if not isinstance(embedding_vector, list) else embedding_vector
                if intent not in result:
                    result[intent] = []
                result[intent].append((phrase, embedding))

        return result

    async def load_all_exemplars(self) -> dict[str, np.ndarray]:
        """Load all cached exemplar embeddings grouped by intent."""
        results = await self.driver.select(db_manager.get_sql("load-all-exemplars"))

        result: dict[str, list[list[float]]] = {}
        for row in results:
            intent = cast("str", row.get("intent"))
            embedding_vector = cast("list[float] | None", row.get("embedding"))
            if embedding_vector is not None:
                embedding = list(embedding_vector) if not isinstance(embedding_vector, list) else embedding_vector
                if intent not in result:
                    result[intent] = []
                result[intent].append(embedding)

        # Convert lists to numpy arrays
        numpy_result: dict[str, np.ndarray] = {}
        for intent, embeddings_list in result.items():
            numpy_result[intent] = np.array(embeddings_list)

        return numpy_result

    async def cache_exemplar(self, intent: str, phrase: str, embedding: list[float]) -> None:
        """Cache a single exemplar embedding.

        SQLSpec automatically handles vector conversions - no need for array.array().
        """
        await self.driver.execute(
            db_manager.get_sql("cache-exemplar"), intent=intent, phrase=phrase, embedding=embedding
        )

    async def populate_cache(self, exemplars: dict[str, list[str]], vertex_ai_service: VertexAIService) -> int:
        """Populate cache with all exemplars. Returns count of embeddings created."""
        count = 0

        for intent, phrases in exemplars.items():
            for phrase in phrases:
                # Check if already cached
                result = await self.driver.select_one_or_none(
                    db_manager.get_sql("get-exemplar-embedding"), intent=intent, phrase=phrase
                )

                # Database returns column names
                embedding_value = result.get("embedding") if result else None
                if embedding_value is None and result:
                    embedding_value = result.get("EMBEDDING")
                if embedding_value is None:
                    # Generate embedding
                    embedding = await vertex_ai_service.get_text_embedding(phrase)
                    await self.cache_exemplar(intent, phrase, embedding)
                    count += 1

                    if count % 10 == 0:
                        logger.info("Cached %d exemplar embeddings...", count)

        logger.info("Populated cache with %d new exemplar embeddings", count)
        return count

    async def add_intent_phrases(self, intent: str, phrases: list[str], vertex_ai_service: VertexAIService) -> int:
        """Add multiple phrases for a specific intent.

        Args:
            intent: Intent name (e.g., "STORE_LOCATION", "PRODUCT_RAG")
            phrases: List of example phrases for this intent
            vertex_ai_service: Service for generating embeddings

        Returns:
            Count of new phrases added
        """
        count = 0

        for phrase in phrases:
            embedding = await vertex_ai_service.get_text_embedding(phrase)
            await self.cache_exemplar(intent, phrase, embedding)
            count += 1

            if count % 10 == 0:
                logger.info("Added %d phrases for intent '%s'...", count, intent)

        logger.info("Added %d new phrases for intent '%s'", count, intent)
        return count

    async def add_new_intent(self, intent: str, phrases: list[str], vertex_ai_service: VertexAIService) -> int:
        """Add a completely new intent with its phrases.

        This is a convenience method that wraps add_intent_phrases.

        Args:
            intent: New intent name (e.g., "ORDER_STATUS", "FEEDBACK")
            phrases: List of example phrases for this intent
            vertex_ai_service: Service for generating embeddings

        Returns:
            Count of phrases added
        """
        logger.info("Adding new intent '%s' with %d phrases", intent, len(phrases))
        return await self.add_intent_phrases(intent, phrases, vertex_ai_service)
