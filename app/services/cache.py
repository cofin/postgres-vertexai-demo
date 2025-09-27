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
            sql.select(
                "id", "cache_key", "response_data", "expires_at", "created_at"
            ).from_("response_cache").where_eq(
                "cache_key", cache_key
            ).where(
                "(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
            ),
            schema_type=ResponseCache,
        )

    async def set_cached_response(
        self,
        cache_key: str,
        response_data: dict[str, Any],
        ttl_minutes: int = 5
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
            sql.insert("response_cache").columns(
                "cache_key", "response_data", "expires_at"
            ).values(
                cache_key=cache_key,
                response_data=response_data,
                expires_at=expires_at,
            ).on_conflict("cache_key").do_update(
                response_data=sql.raw("EXCLUDED.response_data"),
                expires_at=sql.raw("EXCLUDED.expires_at"),
                created_at=sql.raw("CURRENT_TIMESTAMP"),
            ).returning(
                "id", "cache_key", "response_data", "expires_at", "created_at"
            ),
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
            sql.select(
                "id", "cache_key", "response_data", "expires_at", "created_at"
            ).from_("response_cache").where_eq("id", cache_id),
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
            sql.select(
                "id", "text_hash", "embedding", "model", "hit_count", "last_accessed", "created_at"
            ).from_("embedding_cache").where_eq(
                "text_hash", text_hash
            ).where_eq(
                "model", model_name
            ),
            schema_type=EmbeddingCache,
        )

        if result:
            # Update hit count and last accessed
            await self.driver.execute(
                sql.update("embedding_cache").set(
                    hit_count=sql.raw("hit_count + 1"),
                    last_accessed=sql.raw("CURRENT_TIMESTAMP")
                ).where_eq("id", result.id)
            )

        return result

    async def set_cached_embedding(
        self,
        text: str,
        embedding: list[float],
        model_name: str,
    ) -> EmbeddingCache:
        """Cache an embedding.

        Args:
            text: Text that was embedded
            embedding: The embedding vector
            model_name: Model used for embedding

        Returns:
            Created cache entry
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Get result WITHOUT the embedding field to avoid vector type serialization issues
        result = await self.driver.select_one(
            sql.insert("embedding_cache").columns(
                "text_hash", "embedding", "model", "hit_count", "last_accessed"
            ).values(
                text_hash=text_hash,
                embedding=embedding,
                model=model_name,
                hit_count=1,
                last_accessed=sql.raw("CURRENT_TIMESTAMP"),
            ).on_conflict("text_hash", "model").do_update(
                embedding=sql.raw("EXCLUDED.embedding"),
                hit_count=sql.raw("embedding_cache.hit_count + 1"),
                last_accessed=sql.raw("CURRENT_TIMESTAMP"),
            ).returning(
                "id", "text_hash", "model", "hit_count", "last_accessed", "created_at"
                # Note: "embedding" field removed from RETURNING to avoid vector deserialization issue
            )
        )

        # Manually construct the complete object with the embedding we already have
        return EmbeddingCache(
            id=result["id"],
            text_hash=result["text_hash"],
            embedding=embedding,  # Use the embedding we already have
            model=result["model"],
            hit_count=result["hit_count"],
            last_accessed=result["last_accessed"],
            created_at=result["created_at"],
        )

    async def invalidate_cache(self, cache_type: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            cache_type: Type of cache to clear ('response', 'embedding', or None for all)

        Returns:
            Number of records deleted
        """
        deleted_count = 0

        if cache_type in (None, "response"):
            result = await self.driver.execute("DELETE FROM response_cache")
            deleted_count += result.rowcount if result.rowcount else 0

        if cache_type in (None, "embedding"):
            result = await self.driver.execute("DELETE FROM embedding_cache")
            deleted_count += result.rowcount if result.rowcount else 0

        return deleted_count

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of records deleted
        """
        result = await self.driver.execute(
            "DELETE FROM response_cache WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP"
        )
        return result.rowcount if result.rowcount else 0

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        response_count = await self.driver.select_value(
            "SELECT COUNT(*) FROM response_cache"
        )
        embedding_count = await self.driver.select_value(
            "SELECT COUNT(*) FROM embedding_cache"
        )
        embedding_hits = await self.driver.select_value(
            "SELECT COALESCE(SUM(hit_count), 0) FROM embedding_cache"
        )

        return {
            "response_cache_entries": response_count,
            "embedding_cache_entries": embedding_count,
            "total_embedding_hits": embedding_hits,
        }
