"""Product service for managing product data and vector search."""

from __future__ import annotations

from typing import Any

from app.schemas import Product, ProductCreate, ProductSearchResult, ProductUpdate
from app.services.base import SQLSpecService


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
