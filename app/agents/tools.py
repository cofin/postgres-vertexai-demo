"""ADK Tools for Coffee Assistant Agents.

This module defines async functions that can be used directly as Google ADK tools.
The LlmAgent can use raw async functions as tools - no wrapper classes needed.
Function docstrings serve as descriptions for the LLM.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.services.chat import ChatService
    from app.services.embedding import EmbeddingService
    from app.services.intent import IntentService
    from app.services.metrics import MetricsService
    from app.services.product import ProductService


def create_vector_search_tool(
    product_service: ProductService,
    embedding_service: EmbeddingService,
) -> Callable[[str, int, float], list[dict[str, Any]]]:
    """Create vector search tool for product similarity search."""

    async def search_products_by_vector(
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Search for coffee products using vector similarity.

        Find products that match the customer's query using semantic similarity search.

        Args:
            query: Customer's product query or description
            limit: Maximum number of products to return (1-20, default 5)
            similarity_threshold: Minimum similarity score 0.0-1.0 (default 0.7)

        Returns:
            List of matching products with details and similarity scores
        """
        # Generate embedding for query
        query_embedding = await embedding_service.get_text_embedding(query)

        # Search for similar products
        products = await product_service.vector_similarity_search(
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

    return search_products_by_vector


def create_product_lookup_tool(product_service: ProductService) -> Callable[[str], dict[str, Any]]:
    """Create product lookup tool for direct product retrieval."""

    async def get_product_details(product_id: str) -> dict[str, Any]:
        """Get detailed information about a specific product by ID or name.

        Look up a specific product using either its UUID or name.

        Args:
            product_id: Product UUID or name to look up

        Returns:
            Product details with id, name, description, price, and metadata, or error message
        """
        try:
            # Try UUID lookup first (UUID string is 36 characters with hyphens)
            uuid_length = 36
            if len(product_id) == uuid_length and "-" in product_id:
                product = await product_service.get_by_id(uuid.UUID(product_id))
            else:
                # Try name lookup
                products = await product_service.search_by_name(product_id, limit=1)
                product = products[0] if products else None

            if not product:
                return {"error": "Product not found"}

            return {
                "id": str(product.id),
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
                "metadata": product.metadata or {},
            }

        except (ValueError, TypeError, AttributeError) as e:
            return {"error": f"Failed to retrieve product: {e!s}"}

    return get_product_details


def create_session_management_tool(chat_service: ChatService) -> Callable[[str, str | None, str], dict[str, Any]]:
    """Create session management tool for conversation context."""

    async def manage_session(
        user_id: str,
        session_id: str | None = None,
        action: str = "get"
    ) -> dict[str, Any]:
        """Get or create user session for conversation tracking.

        Manage chat sessions for users to maintain conversation context.

        Args:
            user_id: User identifier
            session_id: Optional existing session UUID
            action: Action to perform - get, create, or update (default: get)

        Returns:
            Session information with session_id, user_id, persona, and timestamps
        """
        try:
            if action == "create" or not session_id:
                # For simplicity, return a fallback session
                return {
                    "session_id": f"session_{user_id}",
                    "user_id": user_id,
                    "persona": "enthusiast",
                    "created_at": "2024-01-01T00:00:00Z",
                }

            if action == "get" and session_id:
                session = await chat_service.get_session_by_session_id(session_id)
                if not session:
                    return {"error": "Session not found"}

                return {
                    "session_id": str(session.id),
                    "user_id": session.user_id,
                    "persona": "enthusiast",
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "last_activity": session.updated_at.isoformat() if session.updated_at else None,
                }

        except (ValueError, TypeError, AttributeError) as e:
            return {"error": f"Session management failed: {e!s}"}
        else:
            # No valid action matched
            return {"error": "Invalid action or missing session_id"}

    return manage_session


def create_conversation_history_tool(chat_service: ChatService) -> Callable[[str, int], dict[str, Any]]:
    """Create tool to retrieve conversation history."""

    async def get_conversation_history(
        session_id: str,
        limit: int = 10
    ) -> dict[str, Any]:
        """Get recent conversation history for context.

        Retrieve previous messages from a chat session to provide conversation context.

        Args:
            session_id: Session UUID
            limit: Maximum number of messages to retrieve (1-50, default 10)

        Returns:
            Conversation history with messages, count, and session info
        """
        try:
            history = await chat_service.get_conversation_history(
                session_id=uuid.UUID(session_id),
                limit=limit
            )

            return {
                "session_id": session_id,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    }
                    for msg in history
                ],
                "count": len(history),
            }

        except (ValueError, TypeError, AttributeError) as e:
            return {"error": f"Failed to retrieve history: {e!s}"}

    return get_conversation_history


def create_intent_classification_tool(intent_service: IntentService) -> Callable[[str], dict[str, Any]]:
    """Create intent classification tool for query routing."""

    async def classify_query_intent(query: str) -> dict[str, Any]:
        """Classify user query intent using vector similarity.

        Determine what type of response a user query requires using semantic similarity.

        Args:
            query: User's message to classify

        Returns:
            Intent classification with intent type, confidence score, and matched exemplar phrase
        """
        try:
            result = await intent_service.classify_intent(query)

            return {
                "query": query,
                "intent": result.intent,
                "confidence": float(result.confidence),
                "exemplar_phrase": result.exemplar_phrase,
                "embedding_cache_hit": result.embedding_cache_hit,
                "fallback_used": result.fallback_used,
            }

        except (ValueError, TypeError, AttributeError) as e:
            return {
                "query": query,
                "intent": "GENERAL_CONVERSATION",
                "confidence": 0.5,
                "exemplar_phrase": "",
                "embedding_cache_hit": False,
                "fallback_used": True,
                "error": str(e),
            }

    return classify_query_intent


def create_metrics_recording_tool(metrics_service: MetricsService) -> Callable[[str, str, str, float, int, int, bool, str], dict[str, Any]]:
    """Create metrics recording tool for performance tracking."""

    async def record_agent_metrics(
        session_id: str,
        query: str,
        intent: str,
        confidence: float,
        response_time_ms: int,
        products_found: int = 0,
        cache_hit: bool = False,
        exemplar_used: str = "",
    ) -> dict[str, Any]:
        """Record agent interaction metrics for performance tracking.

        Track performance metrics for agent interactions and analytics.

        Args:
            session_id: Session UUID
            query: User query
            intent: Detected intent type
            confidence: Intent confidence score (0.0-1.0)
            response_time_ms: Total response time in milliseconds
            products_found: Number of products found (default 0)
            cache_hit: Whether embedding cache was hit (default False)
            exemplar_used: Intent exemplar phrase used (default "")

        Returns:
            Metrics recording result with success status
        """
        try:
            await metrics_service.record_search_metric(
                session_id=uuid.UUID(session_id) if session_id != "fallback" else None,
                query=query,
                intent=intent,
                results_count=products_found,
                response_time_ms=response_time_ms,
                similarity_threshold=0.7,  # Default threshold used
            )
        except (ValueError, TypeError, AttributeError) as e:
            return {"success": False, "error": str(e)}
        else:
            return {"success": True, "recorded_at": "now"}

    return record_agent_metrics


class ToolRegistry:
    """Registry for all ADK tools used by agents."""

    def __init__(
        self,
        product_service: ProductService,
        chat_service: ChatService,
        embedding_service: EmbeddingService,
        intent_service: IntentService,
        metrics_service: MetricsService,
    ) -> None:
        """Initialize tool registry with services."""
        self.product_service = product_service
        self.chat_service = chat_service
        self.embedding_service = embedding_service
        self.intent_service = intent_service
        self.metrics_service = metrics_service

    @property
    def vector_search_tool(self) -> Callable[[str, int, float], list[dict[str, Any]]]:
        """Get vector search tool function."""
        return create_vector_search_tool(self.product_service, self.embedding_service)

    @property
    def product_lookup_tool(self) -> Callable[[str], dict[str, Any]]:
        """Get product lookup tool function."""
        return create_product_lookup_tool(self.product_service)

    @property
    def session_management_tool(self) -> Callable[[str, str | None, str], dict[str, Any]]:
        """Get session management tool function."""
        return create_session_management_tool(self.chat_service)

    @property
    def conversation_history_tool(self) -> Callable[[str, int], dict[str, Any]]:
        """Get conversation history tool function."""
        return create_conversation_history_tool(self.chat_service)

    @property
    def intent_classification_tool(self) -> Callable[[str], dict[str, Any]]:
        """Get intent classification tool function."""
        return create_intent_classification_tool(self.intent_service)

    @property
    def metrics_recording_tool(self) -> Callable[[str, str, str, float, int, int, bool, str], dict[str, Any]]:
        """Get metrics recording tool function."""
        return create_metrics_recording_tool(self.metrics_service)

    @property
    def all_tools(self) -> list:
        """Get all available tool functions."""
        return [
            self.vector_search_tool,
            self.product_lookup_tool,
            self.session_management_tool,
            self.conversation_history_tool,
            self.intent_classification_tool,
            self.metrics_recording_tool,
        ]
