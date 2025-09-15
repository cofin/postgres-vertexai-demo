"""Product service for managing product data and vector search."""

from __future__ import annotations

from sqlspec import sql

from app.config import sqlspec
from app.schemas import Product, ProductCreate, ProductSearchResult, ProductUpdate
from app.services.base import OffsetPagination, SQLSpecService, StatementFilter


class ProductService(SQLSpecService):
    """Handles database operations for products using SQLSpec patterns."""

    async def create_product(self, data: ProductCreate) -> Product:
        """Create a new product.

        Args:
            data: Product creation data

        Returns:
            Created product
        """
        # Convert to dict and insert
        product_data = {
            "name": data.name,
            "description": data.description,
            "price": data.price,
            "category": data.category,
            "sku": data.sku,
            "in_stock": data.in_stock,
            "metadata": data.metadata,
        }

        product_id = await self.driver.select_value(
            sql.insert("products")
            .columns("name", "description", "price", "category", "sku", "in_stock", "metadata")
            .values(**product_data)
            .returning("id")
        )

        return await self.get_product(product_id)

    async def get_product(self, product_id: int) -> Product:
        """Get a product by ID.

        Args:
            product_id: Product ID

        Returns:
            Product data

        Raises:
            ValueError: If product not found
        """
        return await self.get_or_404(
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
            .where_eq("id", product_id),
            schema_type=Product,
            error_message=f"Product {product_id} not found",
        )

    async def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        """Update an existing product.

        Args:
            product_id: Product ID to update
            data: Product update data

        Returns:
            Updated product
        """
        # Build update data excluding unset fields
        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.description is not None:
            update_data["description"] = data.description
        if data.price is not None:
            update_data["price"] = data.price
        if data.category is not None:
            update_data["category"] = data.category
        if data.sku is not None:
            update_data["sku"] = data.sku
        if data.in_stock is not None:
            update_data["in_stock"] = data.in_stock
        if data.metadata is not None:
            update_data["metadata"] = data.metadata

        if update_data:
            update_data["updated_at"] = "NOW()"
            await self.driver.execute(sql.update("product").set(**update_data).where_eq("id", product_id))

        return await self.get_product(product_id)

    async def delete_product(self, product_id: int) -> None:
        """Delete a product.

        Args:
            product_id: Product ID to delete
        """
        await self.driver.execute(sql.delete("product").where_eq("id", product_id))

    async def list_products(self, *filters: StatementFilter) -> OffsetPagination[Product]:
        """List products with pagination and filtering.

        Args:
            *filters: Statement filters to apply

        Returns:
            Paginated list of products
        """
        return await self.paginate(
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
            .order_by("created_at DESC"),
            *filters,
            schema_type=Product,
        )

    async def search_products_by_text(self, search_term: str, limit: int = 10) -> list[Product]:
        """Search products by text using full-text search.

        Args:
            search_term: Text to search for
            limit: Maximum number of results

        Returns:
            List of matching products
        """
        return await self.driver.select(
            sqlspec.get_sql("full-text-search"),
            search_term=search_term,
            limit_count=limit,
            schema_type=Product,
        )

    async def search_products_by_category(self, category: str, limit: int = 10) -> list[Product]:
        """Search products by category.

        Args:
            category: Product category
            limit: Maximum number of results

        Returns:
            List of products in category
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
            .where_eq("category", category)
            .where_eq("in_stock", True)
            .order_by("name")
            .limit(limit),
            schema_type=Product,
        )

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
            sqlspec.get_sql("vector-similarity-search"),
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
            .where("embedding IS NULL")
            .order_by("created_at")
            .limit(limit),
            schema_type=Product,
        )
