"""Product-related schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.base import CamelizedBaseStruct

__all__ = (
    "Product",
    "ProductCreate",
    "ProductSearchResult",
    "ProductUpdate",
)


class Product(CamelizedBaseStruct, omit_defaults=True):
    """Product data schema."""

    id: int
    name: str
    description: str
    price: float
    category: str
    sku: str
    in_stock: bool
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductCreate(CamelizedBaseStruct, omit_defaults=True):
    """Product creation schema."""

    name: str
    description: str
    price: float
    category: str
    sku: str
    in_stock: bool = True
    metadata: dict[str, Any] | None = None


class ProductUpdate(CamelizedBaseStruct, omit_defaults=True):
    """Product update schema."""

    name: str | None = None
    description: str | None = None
    price: float | None = None
    category: str | None = None
    sku: str | None = None
    in_stock: bool | None = None
    metadata: dict[str, Any] | None = None


class ProductSearchResult(CamelizedBaseStruct, omit_defaults=True):
    """Product search result with similarity score."""

    id: int
    name: str
    description: str
    price: float
    category: str
    sku: str
    in_stock: bool
    similarity_score: float
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
