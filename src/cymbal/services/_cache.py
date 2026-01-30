"""Cache service for managing response and embedding cache."""

from __future__ import annotations

import hashlib
from typing import Any

from cymbal.schemas import EmbeddingCache, ResponseCache
from cymbal.services.base import SQLSpecService


class CacheService(SQLSpecService):
    """Handles database operations for response and embedding cache."""

    async def get_cached_response(self, cache_key: str) -> ResponseCache | None:
        """Get cached response by key.

        Args:
            cache_key: Cache key to lookup

        Returns:
            Cached response or None if not found or expired
        """
        return await self.driver.select_one_or_none(
            """
            SELECT id, cache_key, response_data, expires_at, created_at
            FROM response_cache
            WHERE cache_key = :cache_key
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT 1
            """,
            cache_key=cache_key,
            schema_type=ResponseCache,
        )

    async def set_cached_response(
        self,
        cache_key: str,
        response_data: dict[str, Any],
        ttl_minutes: int = 5,
    ) -> ResponseCache:
        """Cache a response with TTL using PostgreSQL UPSERT.

        Args:
            cache_key: Unique cache key
            response_data: Response data to cache (as JSON)
            ttl_minutes: Time to live in minutes

        Returns:
            Created cache entry
        """
        cached_response = await self.driver.select_one(
            """
            INSERT INTO response_cache (cache_key, response_data, expires_at, created_at)
            VALUES (:cache_key, :response_data, NOW() + make_interval(mins => :ttl_minutes), NOW())
            ON CONFLICT (cache_key) DO UPDATE SET
                response_data = EXCLUDED.response_data,
                expires_at = EXCLUDED.expires_at,
                created_at = NOW()
            RETURNING id, cache_key, response_data, expires_at, created_at
            """,
            cache_key=cache_key,
            response_data=response_data,
            ttl_minutes=ttl_minutes,
            schema_type=ResponseCache,
        )

        await self.driver.commit()

        return cached_response

    async def get_response_cache_by_id(self, cache_id: int) -> ResponseCache:
        """Get response cache entry by ID.

        Args:
            cache_id: Cache entry ID

        Returns:
            Cache entry

        Raises:
            ValueError: If cache entry not found
        """
        return await self.get_or_404(
            """
            SELECT id, cache_key, response_data, expires_at, created_at
            FROM response_cache
            WHERE id = :cache_id
            """,
            cache_id=cache_id,
            schema_type=ResponseCache,
            error_message=f"Cache entry {cache_id} not found",
        )

    async def get_cached_embedding(self, text: str, model_name: str) -> EmbeddingCache | None:
        """Get cached embedding for text.

        Args:
            text: Text that was embedded
            model_name: Embedding model name

        Returns:
            Cached embedding or None if not found
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        result = await self.driver.select_one_or_none(
            """
            SELECT id, text_hash, embedding, model, hit_count, last_accessed, created_at
            FROM embedding_cache
            WHERE text_hash = :text_hash
              AND model = :model_name
            """,
            text_hash=text_hash,
            model_name=model_name,
            schema_type=EmbeddingCache,
        )

        if result:
            await self.driver.execute(
                """
                UPDATE embedding_cache
                SET hit_count = hit_count + 1,
                    last_accessed = NOW()
                WHERE id = :result_id
                """,
                result_id=result.id,
            )
            await self.driver.commit()

        return result

    async def set_cached_embedding(
        self,
        text: str,
        embedding: list[float],
        model_name: str,
    ) -> EmbeddingCache:
        """Cache an embedding using PostgreSQL UPSERT.

        Args:
            text: Text that was embedded
            embedding: The embedding vector
            model_name: Model used for embedding

        Returns:
            Created cache entry
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        cached_embedding = await self.driver.select_one(
            """
            INSERT INTO embedding_cache (text_hash, embedding, model, hit_count, last_accessed, created_at)
            VALUES (:text_hash, :embedding, :model_name, 1, NOW(), NOW())
            ON CONFLICT (text_hash, model) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                last_accessed = NOW()
            RETURNING id, text_hash, embedding, model, hit_count, last_accessed, created_at
            """,
            text_hash=text_hash,
            embedding=embedding,
            model_name=model_name,
            schema_type=EmbeddingCache,
        )

        await self.driver.commit()

        return cached_embedding

    async def invalidate_cache(self, cache_type: str | None = None, include_exemplars: bool = False) -> int:
        """Invalidate cache entries.

        Args:
            cache_type: Type of cache to clear ('response', 'embedding', or None for all)
            include_exemplars: Whether to also clear intent exemplar embeddings (slow to regenerate)

        Returns:
            Number of records deleted
        """
        deleted_count = 0

        if cache_type in (None, "response"):
            result = await self.driver.execute("DELETE FROM response_cache")
            deleted_count += result.rows_affected

        if cache_type in (None, "embedding"):
            result = await self.driver.execute("DELETE FROM embedding_cache")
            deleted_count += result.rows_affected

        # Only clear exemplars if explicitly requested (expensive to regenerate)
        if include_exemplars:
            result = await self.driver.execute("UPDATE intent_exemplar SET embedding = NULL")
            deleted_count += result.rows_affected

        return deleted_count

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of records deleted
        """
        result = await self.driver.execute(
            "DELETE FROM response_cache WHERE expires_at IS NOT NULL AND expires_at < NOW()",
        )
        return result.rows_affected

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics including hit rate
        """
        response_count = await self.driver.select_value("SELECT COUNT(*) FROM response_cache")
        embedding_count = await self.driver.select_value("SELECT COUNT(*) FROM embedding_cache")
        embedding_hits = await self.driver.select_value("SELECT COALESCE(SUM(hit_count), 0) FROM embedding_cache")

        # Calculate cache hit rate (percentage of requests that hit the cache)
        # This is an approximation based on embedding cache hits vs total embedding entries
        cache_hit_rate = 0.0
        if embedding_count and embedding_count > 0:
            cache_hit_rate = (embedding_hits / max(embedding_count, 1)) * 100

        return {
            "response_cache_entries": response_count,
            "embedding_cache_entries": embedding_count,
            "total_embedding_hits": embedding_hits,
            "cache_hit_rate": cache_hit_rate,
        }

    async def get(self, cache_key: str) -> dict[str, Any] | None:
        """Simple cache get method.

        Args:
            cache_key: Cache key to lookup

        Returns:
            Cached data or None if not found
        """
        cached = await self.get_cached_response(cache_key)
        return cached.response_data if cached else None

    async def set(self, cache_key: str, data: dict[str, Any], ttl: int = 5) -> None:
        """Simple cache set method.

        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time to live in minutes
        """
        await self.set_cached_response(cache_key, data, ttl)

    async def set_query_state(
        self,
        query_id: str,
        state: dict[str, Any],
        ttl_minutes: int = 5,
    ) -> None:
        """Store query state for streaming endpoint.

        Args:
            query_id: Unique query identifier
            state: Query state data to cache
            ttl_minutes: Time to live in minutes
        """
        cache_key = f"query:{query_id}"
        await self.set_cached_response(cache_key, state, ttl_minutes)

    async def get_query_state(self, query_id: str) -> dict[str, Any] | None:
        """Retrieve query state for streaming.

        Args:
            query_id: Unique query identifier

        Returns:
            Query state data or None if not found or expired
        """
        cache_key = f"query:{query_id}"
        cached = await self.get_cached_response(cache_key)
        return cached.response_data if cached else None

    async def delete_query_state(self, query_id: str) -> None:
        """Clean up query state after streaming completes.

        Args:
            query_id: Unique query identifier
        """
        cache_key = f"query:{query_id}"
        await self.driver.execute(
            "DELETE FROM response_cache WHERE cache_key = :cache_key",
            cache_key=cache_key,
        )
        await self.driver.commit()
