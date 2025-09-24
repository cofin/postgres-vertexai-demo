"""ADK Tool Functions - Thin wrappers around AgentToolsService.

These functions provide the ADK tool interface while delegating
to the AgentToolsService for business logic.
"""

from __future__ import annotations

from typing import Any

from app.config import db, service_locator, sqlspec
from app.services.adk.tool_service import AgentToolsService


async def search_products_by_vector(
    query: str,
    limit: int = 5,
    similarity_threshold: float = 0.7
) -> list[dict[str, Any]]:
    """Search for coffee products using vector similarity with fresh session.

    Args:
        query: Customer's product query or description
        limit: Maximum number of products to return (1-20, default 5)
        similarity_threshold: Minimum similarity score 0.0-1.0 (default 0.7)

    Returns:
        List of matching products with details and similarity scores
    """
    async with sqlspec.provide_session(db) as session:
        tools_service = service_locator.get(AgentToolsService, session)
        return await tools_service.search_products_by_vector(query, limit, similarity_threshold)


async def get_product_details(product_id: str) -> dict[str, Any]:
    """Get detailed information about a specific product by ID or name with fresh session.

    Args:
        product_id: Product UUID or name to look up

    Returns:
        Product details or error message
    """
    async with sqlspec.provide_session(db) as session:
        tools_service = service_locator.get(AgentToolsService, session)
        return await tools_service.get_product_details(product_id)


async def classify_intent(query: str) -> dict[str, Any]:
    """Classify user intent using vector-based classification with fresh session.

    Args:
        query: User's message to classify

    Returns:
        Intent classification results
    """
    async with sqlspec.provide_session(db) as session:
        tools_service = service_locator.get(AgentToolsService, session)
        return await tools_service.classify_intent(query)


async def get_conversation_history(
    session_id: str,
    limit: int = 10
) -> list[dict[str, Any]]:
    """Get recent conversation history with fresh session.

    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return

    Returns:
        List of conversation messages
    """
    async with sqlspec.provide_session(db) as session:
        tools_service = service_locator.get(AgentToolsService, session)
        return await tools_service.get_conversation_history(session_id, limit)


async def record_search_metric(
    session_id: str,
    query_text: str,
    intent: str,
    response_time_ms: float,
    vector_search_time_ms: int = 0,
    vector_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record metrics for search performance with fresh session.

    Args:
        session_id: Session identifier
        query_text: The search query
        intent: Detected intent
        response_time_ms: Total response time
        vector_search_time_ms: Time spent on vector search
        vector_results: Vector search results

    Returns:
        Status of metric recording
    """
    async with sqlspec.provide_session(db) as session:
        tools_service = service_locator.get(AgentToolsService, session)
        return await tools_service.record_search_metric(
            session_id=session_id,
            query_text=query_text,
            intent=intent,
            vector_results=vector_results or [],
            total_response_time_ms=int(response_time_ms),
            vector_search_time_ms=vector_search_time_ms,
        )


# List of all available tool functions
ALL_TOOLS = [
    search_products_by_vector,
    get_product_details,
    classify_intent,
    get_conversation_history,
    record_search_metric,
]