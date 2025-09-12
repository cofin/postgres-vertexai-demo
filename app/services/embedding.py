"""Embedding management service with caching support."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.services.base import SQLSpecService
from app.services.cache import CacheService
from app.services.vertex_ai import VertexAIService

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase

logger = structlog.get_logger()


class EmbeddingService(SQLSpecService):
    """Service for managing embeddings with caching.
    
    Inherits from SQLSpecService to use SQLSpec patterns for database operations.
    Manages both embedding generation and caching with two-tier architecture.
    """

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize embedding service.

        Args:
            driver: Database driver for cache operations
        """
        super().__init__(driver)
        self.vertex_ai = VertexAIService()
        self.cache_service = CacheService(driver)
        self._memory_cache: dict[str, list[float]] = {}  # Memory tier cache

    async def get_text_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> list[float]:
        """Get embedding for text with optional caching.

        Args:
            text: Text to embed
            use_cache: Whether to use caching

        Returns:
            Embedding vector
        """
        model_name = self.vertex_ai.settings.vertex_ai.EMBEDDING_MODEL

        # Check cache first if enabled
        if use_cache:
            # Check memory cache first
            cache_key = f"{text}:{model_name}"
            if cache_key in self._memory_cache:
                logger.debug(
                    "Using memory cached embedding",
                    text_length=len(text),
                    model=model_name,
                )
                return self._memory_cache[cache_key]

            # Check database cache
            cached = await self.cache_service.get_cached_embedding(text, model_name)
            if cached:
                # Store in memory cache for next time
                self._memory_cache[cache_key] = cached.embedding_data
                logger.debug(
                    "Using database cached embedding",
                    text_length=len(text),
                    model=model_name,
                )
                return cached.embedding_data

        # Generate new embedding
        embedding = await self.vertex_ai.get_text_embedding(text)

        # Cache the embedding if caching is enabled
        if use_cache:
            try:
                # Store in both memory and database cache
                cache_key = f"{text}:{model_name}"
                self._memory_cache[cache_key] = embedding
                await self.cache_service.set_cached_embedding(text, embedding, model_name)
                logger.debug(
                    "Cached new embedding",
                    text_length=len(text),
                    model=model_name,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Failed to cache embedding",
                    text_length=len(text),
                    model=model_name,
                    error=str(e),
                )

        return embedding

    async def get_batch_embeddings(
        self,
        texts: list[str],
        use_cache: bool = True
    ) -> list[list[float]]:
        """Get embeddings for multiple texts with caching.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use caching

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        model_name = self.vertex_ai.settings.vertex_ai.EMBEDDING_MODEL
        embeddings = []
        texts_to_generate = []
        text_indices = []

        # Check cache for each text if enabled
        if use_cache:
            for i, text in enumerate(texts):
                cache_key = f"{text}:{model_name}"

                # Check memory cache first
                if cache_key in self._memory_cache:
                    embeddings.append(self._memory_cache[cache_key])
                    logger.debug(
                        "Using memory cached embedding",
                        text_index=i,
                        text_length=len(text),
                    )
                else:
                    # Check database cache
                    cached = await self.cache_service.get_cached_embedding(text, model_name)
                    if cached:
                        # Store in memory cache for next time
                        self._memory_cache[cache_key] = cached.embedding_data
                        embeddings.append(cached.embedding_data)
                        logger.debug(
                            "Using database cached embedding",
                            text_index=i,
                            text_length=len(text),
                        )
                    else:
                        embeddings.append([])  # Placeholder
                        texts_to_generate.append(text)
                        text_indices.append(i)
        else:
            texts_to_generate = texts
            text_indices = list(range(len(texts)))
            embeddings = [[]] * len(texts)

        # Generate embeddings for uncached texts
        if texts_to_generate:
            logger.debug(
                "Generating embeddings",
                count=len(texts_to_generate),
                total=len(texts),
            )

            new_embeddings = await self.vertex_ai.get_batch_embeddings(texts_to_generate)

            # Cache new embeddings and fill results
            for text_idx, text, embedding in zip(
                text_indices, texts_to_generate, new_embeddings, strict=False
            ):
                embeddings[text_idx] = embedding

                # Cache the embedding if caching is enabled
                if use_cache:
                    try:
                        # Store in both memory and database cache
                        cache_key = f"{text}:{model_name}"
                        self._memory_cache[cache_key] = embedding
                        await self.cache_service.set_cached_embedding(text, embedding, model_name)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "Failed to cache embedding",
                            text_index=text_idx,
                            text_length=len(text),
                            error=str(e),
                        )

        return embeddings

    async def embed_product_descriptions(
        self,
        products: list[dict[str, Any]],
        use_cache: bool = True
    ) -> list[list[float]]:
        """Generate embeddings for product descriptions.

        Args:
            products: List of product dicts with 'name' and 'description'
            use_cache: Whether to use caching

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

        return await self.get_batch_embeddings(texts, use_cache)

    async def similarity_search_embedding(self, query: str) -> list[float]:
        """Get embedding optimized for similarity search.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # For search queries, we might want to add context
        search_text = f"Search query: {query}"

        return await self.get_text_embedding(search_text, use_cache=True)

    def get_embedding_dimensions(self) -> int:
        """Get embedding vector dimensions."""
        return self.vertex_ai.get_embedding_dimensions()

    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self.vertex_ai.is_initialized
