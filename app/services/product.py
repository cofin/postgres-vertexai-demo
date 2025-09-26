"""Product service for managing product data and vector search."""

from __future__ import annotations

from sqlspec import sql

from app.schemas import Product, ProductSearchResult
from app.services.base import SQLSpecService


class ProductService(SQLSpecService):
    """Handles database operations for products using SQLSpec patterns."""

    async def vector_similarity_search(
        self, query_embedding: list[float], similarity_threshold: float = 0.7, limit: int = 5
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

    async def update_product_embedding(self, product_id: int, embedding: list[float]) -> None:
        """Update product embedding vector.

        Args:
            product_id: Product ID
            embedding: Embedding vector (768 dimensions)
        """
        await self.driver.execute(
            sql.update("product").set(embedding=embedding, updated_at=sql.raw("NOW()")).where_eq("id", product_id)
        )

    async def get_products_without_embeddings(self, limit: int = 100) -> list[Product]:
        """Get products that don't have embeddings yet.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of products without embeddings
        """
        return await self.driver.select(
            sql.select(
                "id",
                "name",
                "description",
                "price",
                "category",
                "sku",
                "in_stock",
                "metadata",
                "created_at",
                "updated_at",
            )
            .from_("product")
            .where_is_null("embedding")
            .order_by("created_at")
            .limit(limit),
            schema_type=Product,
        )
