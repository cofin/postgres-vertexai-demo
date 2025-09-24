"""Agent Tools Service containing business logic for ADK tool operations.

This service consolidates all the business logic for agent tools, ensuring
clean separation between ADK integration and core functionality.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from app.services.chat import ChatService
    from app.services.exemplar import ExemplarService
    from app.services.intent import IntentService
    from app.services.metrics import MetricsService
    from app.services.product import ProductService
    from app.services.vertex_ai import VertexAIService

logger = structlog.get_logger()


class AgentToolsService(SQLSpecService):
    """Service containing all agent tool business logic.

    This service acts as a facade over the other services, providing
    high-level operations for agent tools while maintaining clean
    session management.
    """

    def __init__(
        self,
        driver: Any,
        product_service: ProductService,
        chat_service: ChatService,
        metrics_service: MetricsService,
        intent_service: IntentService,
        vertex_ai_service: VertexAIService,
    ) -> None:
        """Initialize agent tools service.

        Args:
            driver: Database driver
            product_service: Service for product operations
            chat_service: Service for chat operations
            metrics_service: Service for metrics operations
            intent_service: Service for intent classification
            vertex_ai_service: Service for AI operations
        """
        super().__init__(driver)
        self.product_service = product_service
        self.chat_service = chat_service
        self.metrics_service = metrics_service
        self.intent_service = intent_service
        self.vertex_ai_service = vertex_ai_service

    async def search_products_by_vector(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Search for coffee products using vector similarity.

        Args:
            query: Customer's product query or description
            limit: Maximum number of products to return (1-20, default 5)
            similarity_threshold: Minimum similarity score 0.0-1.0 (default 0.7)

        Returns:
            List of matching products with details and similarity scores
        """
        # Generate embedding for query
        query_embedding = await self.vertex_ai_service.get_text_embedding(query)

        # Search for similar products
        products = await self.product_service.vector_similarity_search(
            query_embedding=query_embedding,
            similarity_threshold=similarity_threshold,
            limit=limit
        )

        return [
            {
                "id": str(product.id),
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
                "similarity_score": float(product.similarity_score),
                "metadata": product.metadata or {},
            }
            for product in products
        ]

    async def get_product_details(self, product_id: str) -> dict[str, Any]:
        """Get detailed information about a specific product by ID or name.

        Args:
            product_id: Product UUID or name to look up

        Returns:
            Product details or error message
        """
        try:
            # Try UUID lookup first (UUID string is 36 characters with hyphens)
            uuid_length = 36
            if len(product_id) == uuid_length and "-" in product_id:
                product = await self.product_service.get_by_id(uuid.UUID(product_id))
            else:
                # Try name lookup
                products = await self.product_service.search_by_name(product_id, limit=1)
                product = products[0] if products else None

            if not product:
                return {"error": "Product not found"}

            return {
                "id": str(product.id),
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
                "category": product.category,
                "in_stock": product.in_stock,
                "metadata": product.metadata or {},
            }
        except (ValueError, TypeError, AttributeError) as e:
            return {"error": f"Failed to lookup product: {e!s}"}

    async def classify_intent(self, query: str) -> dict[str, Any]:
        """Classify user intent using vector-based classification.

        Args:
            query: User's message to classify

        Returns:
            Intent classification results
        """
        try:
            result = await self.intent_service.classify_intent(query)
            return {
                "intent": result.intent,
                "confidence": float(result.confidence),
                "exemplar_phrase": result.exemplar_phrase,
                "embedding_cache_hit": result.embedding_cache_hit,
                "fallback_used": result.fallback_used,
            }
        except (ValueError, TypeError, AttributeError) as e:
            return {
                "intent": "GENERAL_CONVERSATION",
                "confidence": 0.5,
                "exemplar_phrase": "",
                "embedding_cache_hit": False,
                "fallback_used": True,
                "error": str(e),
            }

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of conversation messages
        """
        try:
            # Convert session_id to UUID if it's not already
            if isinstance(session_id, str):
                session_uuid = uuid.UUID(session_id)
            else:
                session_uuid = session_id

            conversations = await self.chat_service.get_recent_conversations(
                session_id=session_uuid,
                limit=limit
            )

            return [
                {
                    "id": str(conv.id),
                    "user_message": conv.user_message,
                    "assistant_response": conv.assistant_response,
                    "created_at": conv.created_at.isoformat(),
                    "response_time_ms": conv.response_time_ms,
                }
                for conv in conversations
            ]
        except (ValueError, TypeError, AttributeError) as e:
            return {"error": f"Failed to retrieve history: {e!s}"}

    async def record_search_metric(
        self,
        session_id: str,
        query_text: str,
        intent: str,
        vector_results: list[dict[str, Any]],
        total_response_time_ms: int,
        vector_search_time_ms: int = 0,
    ) -> dict[str, Any]:
        """Record metrics for a search operation.

        Args:
            session_id: Session identifier
            query_text: The search query
            intent: Detected intent
            vector_results: Vector search results
            total_response_time_ms: Total response time
            vector_search_time_ms: Time spent on vector search

        Returns:
            Status of metric recording
        """
        try:
            await self.metrics_service.record_search_metric(
                session_id=session_id,
                query_text=query_text,
                intent=intent,
                vector_search_results=vector_results,
                total_response_time_ms=int(total_response_time_ms),
                vector_search_time_ms=vector_search_time_ms,
            )
        except (ValueError, TypeError, AttributeError) as e:
            return {"status": "failed", "error": str(e)}
        else:
            return {"status": "recorded", "session_id": session_id}