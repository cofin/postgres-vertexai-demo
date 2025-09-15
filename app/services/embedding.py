"""Embedding management service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.services.base import SQLSpecService
from app.services.vertex_ai import VertexAIService

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase

logger = structlog.get_logger()


class EmbeddingService(SQLSpecService):
    """Service for managing embeddings.

    Inherits from SQLSpecService to use SQLSpec patterns for database operations.
    Manages embedding generation.
    """

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize embedding service.

        Args:
            driver: Database driver
        """
        super().__init__(driver)
        self.vertex_ai = VertexAIService()

    async def get_text_embedding(self, text: str) -> list[float]:
        """Get embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        return await self.vertex_ai.get_text_embedding(text)

    async def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.debug(
            "Generating embeddings",
            count=len(texts),
        )

        return await self.vertex_ai.get_batch_embeddings(texts)

    async def embed_product_descriptions(
        self, products: list[dict[str, Any]]
    ) -> list[list[float]]:
        """Generate embeddings for product descriptions.

        Args:
            products: List of product dicts with 'name' and 'description'

        Returns:
            List of embedding vectors
        """
        # Create combined text for each product
        texts = []
        for product in products:
            combined_text = f"{product['name']}: {product['description']}"
            if product.get("category"):
                combined_text += f" (Category: {product['category']})"
            texts.append(combined_text)

        logger.debug(
            "Embedding product descriptions",
            product_count=len(products),
        )

        return await self.get_batch_embeddings(texts)

    async def similarity_search_embedding(self, query: str) -> list[float]:
        """Get embedding optimized for similarity search.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # For search queries, we might want to add context
        search_text = f"Search query: {query}"

        return await self.get_text_embedding(search_text)

    def get_embedding_dimensions(self) -> int:
        """Get embedding vector dimensions."""
        return self.vertex_ai.get_embedding_dimensions()

    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self.vertex_ai.is_initialized
