"""Data schemas using msgspec for high-performance serialization."""

from __future__ import annotations

from app.schemas.cache import EmbeddingCache, ResponseCache
from app.schemas.chat import (
    ChatConversation,
    ChatConversationCreate,
    ChatMessage,
    ChatMessageRequest,
    ChatSession,
    ChatSessionCreate,
)
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
from app.schemas.vector_demo import VectorDemoRequest

__all__ = (
    "ChatConversation",
    "ChatConversationCreate",
    "ChatMessage",
    "ChatMessageRequest",
    "ChatSession",
    "ChatSessionCreate",
    "EmbeddingCache",
    "IntentClassification",
    "IntentExemplar",
    "IntentExemplarCreate",
    "IntentExemplarUpdate",
    "IntentResult",
    "IntentSearchResult",
    "IntentStats",
    "Product",
    "ProductCreate",
    "ProductSearchResult",
    "ProductUpdate",
    "ResponseCache",
    "SearchMetrics",
    "VectorDemoRequest",
)
