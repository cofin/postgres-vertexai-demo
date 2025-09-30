"""Store schema for coffee shop locations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.base import CamelizedBaseStruct

if TYPE_CHECKING:
    from datetime import datetime

__all__ = (
    "Store",
    "StoreCreate",
    "StoreUpdate",
)


class Store(CamelizedBaseStruct, omit_defaults=True):
    """Store data schema."""

    id: int
    name: str
    address: str
    created_at: datetime
    updated_at: datetime
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    hours: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class StoreCreate(CamelizedBaseStruct, omit_defaults=True):
    """Store creation schema."""

    name: str
    address: str
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    hours: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class StoreUpdate(CamelizedBaseStruct, omit_defaults=True):
    """Store update schema."""

    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    hours: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
