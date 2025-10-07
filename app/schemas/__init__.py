"""Data schemas using msgspec for high-performance serialization."""

from app.schemas.base import BaseStruct, CamelizedBaseStruct, Message
from app.schemas.cache import EmbeddingCache, ResponseCache, VectorSearchCache
from app.schemas.chat import ChatMessage, ChatMessageRequest
from app.schemas.intent import (
    IntentClassification,
    IntentExemplar,
    IntentExemplarCreate,
    IntentExemplarUpdate,
    IntentResult,
    IntentSearchResult,
    IntentStats,
)
from app.schemas.metrics import SearchMetrics
from app.schemas.product import Product, ProductCreate, ProductSearchResult, ProductUpdate
from app.schemas.store import Store, StoreCreate, StoreUpdate
from app.schemas.vector_demo import VectorDemoRequest

__all__ = (
    "BaseStruct",
    "CamelizedBaseStruct",
    "ChatMessage",
    "ChatMessageRequest",
    "EmbeddingCache",
    "IntentClassification",
    "IntentExemplar",
    "IntentExemplarCreate",
    "IntentExemplarUpdate",
    "IntentResult",
    "IntentSearchResult",
    "IntentStats",
    "Message",
    "Product",
    "ProductCreate",
    "ProductSearchResult",
    "ProductUpdate",
    "ResponseCache",
    "SearchMetrics",
    "Store",
    "StoreCreate",
    "StoreUpdate",
    "VectorDemoRequest",
    "VectorSearchCache",
)
