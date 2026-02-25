"""Product service using SQLSpec driver patterns."""

from typing import Any

from cymbal.config import db_manager
from cymbal.schemas import Product
from cymbal.services.base import LimitOffsetFilter, SQLSpecService


class ProductService(SQLSpecService):
    """Handles database operations for products using SQLSpec patterns."""

    async def get_all(self) -> list[Product]:
        """Get all products."""
        results: list[Product] = await self.driver.select(db_manager.get_sql("get-all-products"), schema_type=Product)
        return results

    async def get_by_id(self, product_id: int) -> Product | None:
        """Get product by ID."""
        result: Product | None = await self.driver.select_one_or_none(
            db_manager.get_sql("get-product-by-id"), id=product_id, schema_type=Product
        )
        return result

    async def get_by_name(self, name: str) -> Product | None:
        """Get product by name."""
        result: Product | None = await self.driver.select_one_or_none(
            db_manager.get_sql("get-product-by-name"), name=name, schema_type=Product
        )
        return result

    async def get_products_without_embeddings(self, limit: int = 100, offset: int = 0) -> tuple[list[Product], int]:
        """Get products that have null embeddings with pagination."""
        # Use SQLSpecService.paginate which injects LIMIT/OFFSET via AST
        paginated = await self.paginate(
            db_manager.get_sql("get-products-without-embeddings"), LimitOffsetFilter(limit, offset), schema_type=Product
        )
        return paginated.items, paginated.total

    async def search_by_vector(
        self, query_embedding: list[float], limit: int = 10, similarity_threshold: float = 0.5
    ) -> list[dict[str, Any]]:
        """Search products by vector similarity using PostgreSQL/AlloyDB pgvector.

        SQLSpec automatically handles vector conversions - no need for array.array().

        Note: Returns dict instead of Product because includes similarity_score field.
        """
        # PostgreSQL pgvector similarity search
        results: list[dict[str, Any]] = await self.driver.select(
            db_manager.get_sql("search-products-by-vector"),
            query_embedding=query_embedding,
            similarity_threshold=similarity_threshold,
            limit=limit,
        )

        return results

    async def update_embedding(self, product_id: int, embedding: list[float]) -> bool:
        """Update product embedding.

        SQLSpec automatically handles vector conversions - no need for array.array().
        """
        result = await self.driver.execute(
            db_manager.get_sql("update-product-embedding"), id=product_id, embedding=embedding
        )
        await self.driver.commit()
        return bool(result.rows_affected > 0)

    async def create_product(
        self,
        name: str,
        price: float,
        description: str,
        category: str | None = None,
        sku: str | None = None,
        in_stock: bool = True,
        metadata: dict | None = None,
        embedding: list[float] | None = None,
    ) -> Product | None:
        """Create a new product."""
        product = await self.driver.select_one_or_none(
            db_manager.get_sql("create-product"),
            name=name,
            price=price,
            description=description,
            category=category,
            sku=sku,
            in_stock=in_stock,
            metadata=metadata,
            embedding=embedding,
            schema_type=Product,
        )
        if product:
            await self.driver.commit()
        return product

    async def update_product(self, product_id: int, updates: dict[str, Any]) -> Product | None:
        """Update a product."""
        # Build UPDATE statement with safe field mapping
        field_mapping = {
            "name": "name = :name",
            "price": "price = :price",
            "description": "description = :description",
            "category": "category = :category",
            "sku": "sku = :sku",
            "in_stock": "in_stock = :in_stock",
            "metadata": "metadata = :metadata",
        }

        set_clauses = []
        params: dict[str, Any] = {"id": product_id}

        for field, value in updates.items():
            if field in field_mapping:
                set_clauses.append(field_mapping[field])
                params[field] = value

        if not set_clauses:
            return await self.get_by_id(product_id)

        returning_clause = "RETURNING id, name, price, description, category, sku, in_stock, metadata, embedding, created_at, updated_at"
        sql = f"UPDATE product SET {', '.join(set_clauses)}, updated_at = NOW() WHERE id = :id {returning_clause}"

        product = await self.driver.select_one_or_none(sql, schema_type=Product, **params)

        if product:
            await self.driver.commit()
        return product

    async def delete_product(self, product_id: int) -> bool:
        """Delete a product."""
        result = await self.driver.execute(db_manager.get_sql("delete-product"), id=product_id)
        await self.driver.commit()
        return bool(result.rows_affected > 0)
