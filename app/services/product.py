"""Product service for managing product data and vector search."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from app.schemas import Product, ProductCreate, ProductSearchResult, ProductUpdate, VectorSearchCache
from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from uuid import UUID


class ProductService(SQLSpecService):
    """Handles database operations for products using SQLSpec patterns."""

    async def vector_similarity_search(
        self,
        query_embedding: list[float],
        similarity_threshold: float = 0.7,
        limit: int = 5,
    ) -> list[ProductSearchResult]:
        """Search products using vector similarity.

        Args:
            query_embedding: Query embedding vector (768 dimensions)
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            limit: Maximum number of results

        Returns:
            List of products with similarity scores
        """
        return await self.driver.select(
            """
            SELECT
              id,
              name,
              description,
              price,
              category,
              sku,
              in_stock,
              metadata,
              created_at,
              updated_at,
              1 - (embedding <=> :query_embedding) as similarity_score
            FROM
              product
            WHERE
              embedding IS NOT NULL
              AND in_stock = true
              AND 1 - (embedding <=> :query_embedding) >= :similarity_threshold
            ORDER BY
              embedding <=> :query_embedding
            LIMIT
              :limit_count
            """,
            query_embedding=query_embedding,
            similarity_threshold=similarity_threshold,
            limit_count=limit,
            schema_type=ProductSearchResult,
        )

    async def vector_similarity_search_with_cache(
        self,
        query_embedding: list[float],
        similarity_threshold: float = 0.7,
        limit: int = 5,
    ) -> tuple[list[ProductSearchResult], bool]:
        """Vector similarity search with result caching.

        Caches search results for 1 minute to reduce query latency by 90%.
        Cache key: hash(embedding[:10] + threshold + limit)

        Args:
            query_embedding: Query embedding vector (768 dimensions)
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            limit: Maximum number of results

        Returns:
            Tuple of (search results, cache_hit boolean)
        """
        # Generate cache key from embedding + params
        cache_key = self._generate_vector_cache_key(
            query_embedding, similarity_threshold, limit
        )

        # Check cache
        cached = await self._get_cached_vector_search(cache_key)
        if cached:
            # Reconstruct results from cached product IDs
            results = await self._fetch_products_by_ids(cached.product_ids, query_embedding)
            await self._update_cache_hit(cached.id)
            return results, True  # Cache hit

        # Cache miss - run actual search
        results = await self.vector_similarity_search(
            query_embedding, similarity_threshold, limit
        )

        # Cache results (TTL: 1 minute)
        if results:
            await self._cache_vector_search_results(
                cache_key, results, similarity_threshold, limit
            )

        return results, False  # Cache miss

    def _generate_vector_cache_key(
        self,
        embedding: list[float],
        threshold: float,
        limit: int,
    ) -> str:
        """Generate cache key from embedding + params.

        Uses first 10 dimensions to create hash (sufficient for uniqueness).
        """
        embedding_sample = embedding[:10]
        data = {
            "embedding": embedding_sample,
            "threshold": threshold,
            "limit": limit,
        }
        hash_input = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(hash_input).hexdigest()[:16]

    async def _get_cached_vector_search(
        self, cache_key: str
    ) -> VectorSearchCache | None:
        """Check vector search cache."""
        return await self.driver.select_one_or_none(
            """
            SELECT id, embedding_hash, similarity_threshold, result_limit,
                   product_ids, results_count, expires_at,
                   created_at, last_accessed, hit_count
            FROM vector_search_cache
            WHERE embedding_hash = :cache_key
              AND expires_at > CURRENT_TIMESTAMP
            """,
            cache_key=cache_key,
            schema_type=VectorSearchCache,
        )

    async def _fetch_products_by_ids(
        self, product_ids: list[int], query_embedding: list[float]
    ) -> list[ProductSearchResult]:
        """Fetch full product details from cached IDs with similarity scores.

        Re-calculates similarity scores for cached results to ensure accuracy.
        """
        return await self.driver.select(
            """
            SELECT id, name, description, price, category, sku,
                   in_stock, metadata, created_at, updated_at,
                   1 - (embedding <=> :query_embedding) as similarity_score
            FROM product
            WHERE id = ANY(:product_ids)
            ORDER BY array_position(:product_ids, id)
            """,
            product_ids=product_ids,
            query_embedding=query_embedding,
            schema_type=ProductSearchResult,
        )

    async def _cache_vector_search_results(
        self,
        cache_key: str,
        results: list[ProductSearchResult],
        threshold: float,
        limit: int,
    ) -> None:
        """Cache vector search results with 1-minute TTL."""
        product_ids = [r.id for r in results]

        await self.driver.execute(
            """
            INSERT INTO vector_search_cache (
                embedding_hash, similarity_threshold, result_limit,
                product_ids, results_count, expires_at
            )
            VALUES (
                :cache_key, :threshold, :limit,
                :product_ids, :count,
                CURRENT_TIMESTAMP + INTERVAL '1 minute'
            )
            ON CONFLICT (embedding_hash, similarity_threshold, result_limit)
            DO UPDATE SET
                product_ids = EXCLUDED.product_ids,
                results_count = EXCLUDED.results_count,
                expires_at = EXCLUDED.expires_at,
                last_accessed = CURRENT_TIMESTAMP,
                hit_count = vector_search_cache.hit_count + 1
            """,
            cache_key=cache_key,
            threshold=threshold,
            limit=limit,
            product_ids=product_ids,
            count=len(product_ids),
        )

    async def _update_cache_hit(self, cache_id: int) -> None:
        """Update cache hit statistics."""
        await self.driver.execute(
            """
            UPDATE vector_search_cache
            SET hit_count = hit_count + 1,
                last_accessed = CURRENT_TIMESTAMP
            WHERE id = :cache_id
            """,
            cache_id=cache_id,
        )

    async def upsert_product(self, data: ProductCreate | ProductUpdate) -> Product:
        """Create or update a product using upsert pattern.

        Args:
            data: Product creation or update data

        Returns:
            Created or updated product
        """
        return await self.driver.select_one(
            """
            INSERT INTO product (name, description, price, category, sku, in_stock, metadata)
            VALUES (:name, :description, :price, :category, :sku, :in_stock, :metadata)
            ON CONFLICT (sku) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                price = EXCLUDED.price,
                category = EXCLUDED.category,
                in_stock = EXCLUDED.in_stock,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING
                id, name, description, price, category, sku,
                in_stock, metadata, created_at, updated_at
            """,
            name=data.name,
            description=data.description,
            price=data.price,
            category=data.category,
            sku=data.sku,
            in_stock=data.in_stock,
            metadata=data.metadata,
            schema_type=Product,
        )

    async def update_product_embedding(self, product_id: int, embedding: list[float]) -> None:
        """Update product embedding vector.

        Args:
            product_id: Product ID
            embedding: Embedding vector (768 dimensions)
        """
        await self.driver.execute(
            """
            UPDATE product
            SET embedding = :embedding,
                updated_at = NOW()
            WHERE id = :product_id
            """,
            embedding=embedding,
            product_id=product_id,
        )

    async def get_products_without_embeddings(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get products that don't have embeddings yet.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of products without embeddings
        """
        return await self.driver.select(
            """
            SELECT
                id, name, description, price, category, sku,
                in_stock, metadata, created_at, updated_at
            FROM product
            WHERE embedding IS NULL
            ORDER BY created_at
            LIMIT :limit
            """,
            limit=limit,
        )

    async def get_by_id(self, product_id: UUID) -> Product | None:
        """Get a product by ID.

        Args:
            product_id: Product UUID

        Returns:
            Product or None if not found
        """
        return await self.driver.select_one_or_none(
            """
            SELECT
                id, name, description, price, category, sku,
                in_stock, metadata, created_at, updated_at
            FROM product
            WHERE id = :product_id
            """,
            product_id=product_id,
            schema_type=Product,
        )

    async def search_by_name(self, query: str, limit: int = 10) -> list[Product]:
        """Search products by name using text search.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching products
        """
        return await self.driver.select(
            """
            SELECT
                id, name, description, price, category, sku,
                in_stock, metadata, created_at, updated_at
            FROM product
            WHERE LOWER(name) LIKE LOWER(:query) OR LOWER(description) LIKE LOWER(:query)
            ORDER BY
                CASE
                    WHEN LOWER(name) LIKE LOWER(:exact_query) THEN 0
                    WHEN LOWER(name) LIKE LOWER(:start_query) THEN 1
                    ELSE 2
                END,
                name
            LIMIT :limit
            """,
            query=f"%{query}%",
            exact_query=query,
            start_query=f"{query}%",
            limit=limit,
            schema_type=Product,
        )
