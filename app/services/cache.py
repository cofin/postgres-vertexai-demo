"""Cache service for managing response and embedding cache."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlspec import sql

from app.schemas import EmbeddingCache, ResponseCache
from app.services.base import SQLSpecService


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
            sql.select("id", "cache_key", "response_data", "expires_at", "created_at")
            .from_("response_cache")
            .where_eq("cache_key", cache_key)
            .where("(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"),
            schema_type=ResponseCache,
        )

    async def set_cached_response(
        self, cache_key: str, response_data: dict[str, Any], ttl_minutes: int = 5
    ) -> ResponseCache:
        """Cache a response with TTL.

        Args:
            cache_key: Unique cache key
            response_data: Response data to cache (as JSON)
            ttl_minutes: Time to live in minutes

        Returns:
            Created cache entry
        """
        expires_at = sql.raw(f"NOW() + INTERVAL '{ttl_minutes} minutes'")

        return await self.driver.select_one(
            sql.insert("response_cache")
            .columns("cache_key", "response_data", "expires_at")
            .values(
                cache_key=cache_key,
                response_data=response_data,
                expires_at=expires_at,
            )
            .on_conflict("cache_key")
            .do_update(
                response_data=sql.raw("EXCLUDED.response_data"),
                expires_at=sql.raw("EXCLUDED.expires_at"),
                created_at=sql.raw("CURRENT_TIMESTAMP"),
            )
            .returning("id", "cache_key", "response_data", "expires_at", "created_at"),
            schema_type=ResponseCache,
        )

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
            sql.select("id", "cache_key", "response_data", "expires_at", "created_at")
            .from_("response_cache")
            .where_eq("id", cache_id),
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
        text_hash = self._hash_text(text)

        # Get raw result first (embedding will be numpy array from pgvector)
        return await self.driver.select_one_or_none(
            sql.select("id", "text_hash", "embedding", "model", "hit_count", "last_accessed", "created_at")
            .from_("embedding_cache")
            .where_eq("text_hash", text_hash)
            .where_eq("model", model_name),
            schema_type=EmbeddingCache,
        )

    async def set_cached_embedding(self, text: str, embedding: list[float], model_name: str) -> EmbeddingCache:
        """Cache an embedding.

        Args:
            text: Text that was embedded
            embedding: Embedding vector
            model_name: Embedding model name

        Returns:
            Created cache entry
        """
        text_hash = self._hash_text(text)

        return await self.driver.select_one(
            sql.insert("embedding_cache")
            .columns("text_hash", "embedding", "model")
            .values(
                text_hash=text_hash,
                embedding=embedding,
                model=model_name,
            )
            .on_conflict("text_hash")
            .do_update(
                embedding=sql.raw("EXCLUDED.embedding"),
                model=sql.raw("EXCLUDED.model"),
                created_at=sql.raw("CURRENT_TIMESTAMP"),
            )
            .returning("id", "text_hash", "embedding", "model", "hit_count", "last_accessed", "created_at"),
            schema_type=EmbeddingCache,
        )

    async def get_embedding_cache_by_id(self, cache_id: int) -> EmbeddingCache:
        """Get embedding cache entry by ID.

        Args:
            cache_id: Cache entry ID

        Returns:
            Cache entry

        Raises:
            ValueError: If cache entry not found
        """
        result = await self.driver.select_one_or_none(
            sql.select("id", "text_hash", "embedding", "model", "hit_count", "last_accessed", "created_at")
            .from_("embedding_cache")
            .where_eq("id", cache_id),
            schema_type=EmbeddingCache,
        )

        if result is None:
            error_message = f"Embedding cache entry {cache_id} not found"
            raise ValueError(error_message)

        return result

    async def cleanup_expired_responses(self) -> int:
        """Clean up expired response cache entries.

        Returns:
            Number of entries deleted
        """
        result = await self.driver.execute(
            sql.delete("response_cache").where("expires_at IS NOT NULL").where("expires_at < CURRENT_TIMESTAMP")
        )
        return result.rows_affected

    async def cleanup_old_embeddings(self, days_old: int = 90) -> int:
        """Clean up old embedding cache entries.

        Args:
            days_old: Embeddings older than this many days will be deleted

        Returns:
            Number of entries deleted
        """
        result = await self.driver.execute(
            sql.delete("embedding_cache").where(f"created_at < NOW() - INTERVAL '{days_old} days'")
        )
        return result.get_count()

    async def delete_cached_response(self, cache_key: str) -> None:
        """Delete a cached response by key.

        Args:
            cache_key: Cache key to delete
        """
        await self.driver.execute(sql.delete("response_cache").where_eq("cache_key", cache_key))

    async def clear_response_cache(self) -> int:
        """Clear all response cache entries.

        Returns:
            Number of entries deleted
        """
        result = await self.driver.execute(sql.delete("response_cache"))
        return result.get_count()

    async def get_embeddings_by_model(self, model_name: str, limit: int = 100) -> list[EmbeddingCache]:
        """Get all embeddings for a specific model.

        Args:
            model_name: Model name to filter by
            limit: Maximum number of results

        Returns:
            List of embedding cache entries
        """
        return await self.driver.select(
            sql.select("id", "text_hash", "embedding", "model", "hit_count", "last_accessed", "created_at")
            .from_("embedding_cache")
            .where_eq("model", model_name)
            .order_by("created_at DESC")
            .limit(limit),
            schema_type=EmbeddingCache,
        )

    async def delete_cached_embedding(self, text_hash: str, model_name: str) -> None:
        """Delete a cached embedding.

        Args:
            text_hash: Text hash to delete
            model_name: Model name
        """
        await self.driver.execute(
            sql.delete("embedding_cache").where_eq("text_hash", text_hash).where_eq("model", model_name)
        )

    async def delete_embeddings_by_model(self, model_name: str) -> int:
        """Delete all cached embeddings for a model.

        Args:
            model_name: Model name

        Returns:
            Number of entries deleted
        """
        result = await self.driver.execute(sql.delete("embedding_cache").where_eq("model", model_name))
        return result.rows_affected

    async def clear_embedding_cache(self) -> int:
        """Clear all embedding cache entries.

        Returns:
            Number of entries deleted
        """
        result = await self.driver.execute(sql.delete("embedding_cache"))
        return result.rows_affected

    async def increment_embedding_hit(self, text_hash: str, model_name: str) -> None:
        """Increment hit count for an embedding.

        Args:
            text_hash: Text hash
            model_name: Model name
        """
        await self.driver.execute(
            sql.update("embedding_cache")
            .set(
                hit_count=sql.raw("hit_count + 1"),
                last_accessed=sql.raw("CURRENT_TIMESTAMP"),
            )
            .where_eq("text_hash", text_hash)
            .where_eq("model", model_name)
        )

    async def batch_get_embeddings(self, text_hashes: list[str], model_name: str) -> list[EmbeddingCache]:
        """Get multiple embeddings by text hashes.

        Args:
            text_hashes: List of text hashes
            model_name: Model name

        Returns:
            List of embedding cache entries
        """
        return await self.driver.select(
            sql.select("id", "text_hash", "embedding", "model", "hit_count", "last_accessed", "created_at")
            .from_("embedding_cache")
            .where_in("text_hash", text_hashes)
            .where_eq("model", model_name),
            schema_type=EmbeddingCache,
        )

    # Keep the old method name for backward compatibility
    async def invalidate_cache_by_key(self, cache_key: str) -> None:
        """Invalidate a cached response by key.

        Args:
            cache_key: Cache key to invalidate
        """
        await self.delete_cached_response(cache_key)

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return await self.driver.select_one("""
            WITH response_stats AS (
                SELECT
                    COUNT(*) as response_total_entries,
                    COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL THEN 1 END) as response_active_entries,
                    COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as response_expired_entries,
                    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as response_avg_age_seconds
                FROM response_cache
            ),
            embedding_stats AS (
                SELECT
                    COUNT(*) as embedding_total_entries,
                    COUNT(DISTINCT model) as embedding_unique_models,
                    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as embedding_avg_age_seconds
                FROM embedding_cache
            )
            SELECT * FROM response_stats CROSS JOIN embedding_stats
            """)

    @staticmethod
    def _hash_text(text: str) -> str:
        """Generate SHA-256 hash of text for cache key.

        Args:
            text: Text to hash

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def generate_cache_key(self, *parts: str) -> str:
        """Generate a cache key from multiple parts.

        Args:
            *parts: String parts to combine into cache key

        Returns:
            Cache key string
        """
        combined = ":".join(str(part) for part in parts)
        return self._hash_text(combined)
