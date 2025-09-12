"""ADK Agent Orchestrator for Coffee Assistant System.

This module provides the main orchestrator class that manages the ADK agent system,
handles dependency injection, and serves as the primary interface between the
web layer and the agent system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.agents.adk_core import CoffeeAssistantAgent
from app.agents.tools import ToolRegistry

if TYPE_CHECKING:
    from sqlspec import AsyncDriverAdapterBase

    from app.services.cache import CacheService
    from app.services.chat import ChatService
    from app.services.embedding import EmbeddingService
    from app.services.intent import IntentService
    from app.services.metrics import MetricsService
    from app.services.product import ProductService

logger = structlog.get_logger()


class ADKOrchestrator:
    """Main orchestrator for the ADK-based coffee assistant system.

    This class:
    1. Initializes all ADK agents with proper dependencies
    2. Provides the main interface for processing user requests
    3. Manages the tool registry and service dependencies
    4. Handles agent lifecycle and error recovery
    """

    def __init__(
        self,
        product_service: ProductService,
        chat_service: ChatService,
        embedding_service: EmbeddingService,
        intent_service: IntentService,
        metrics_service: MetricsService,
        cache_service: CacheService,
    ) -> None:
        """Initialize the ADK orchestrator with all required services.

        Args:
            product_service: Product database operations
            chat_service: Chat session and conversation management
            embedding_service: Text embedding generation
            intent_service: Intent classification
            metrics_service: Performance metrics tracking
            cache_service: Response and embedding caching
        """
        self.product_service = product_service
        self.chat_service = chat_service
        self.embedding_service = embedding_service
        self.intent_service = intent_service
        self.metrics_service = metrics_service
        self.cache_service = cache_service

        # Initialize tool registry with services
        self.tool_registry = ToolRegistry(
            product_service=product_service,
            chat_service=chat_service,
            embedding_service=embedding_service,
            intent_service=intent_service,
            metrics_service=metrics_service,
        )

        # Initialize main ADK agent
        self.coffee_assistant = CoffeeAssistantAgent(self.tool_registry)

        logger.info(
            "ADK Orchestrator initialized",
            agents_count=4,  # Main + 3 sub-agents
            tools_count=len(self.tool_registry.all_tools),
        )

    async def process_request(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        persona: str = "enthusiast",
    ) -> dict[str, Any]:
        """Process a user request through the ADK agent system.

        This is the main entry point for all user interactions. It routes
        the request through the appropriate agents and returns a complete response.

        Args:
            query: User's message or question
            user_id: Unique user identifier
            session_id: Optional existing session ID
            persona: User persona for tailored responses

        Returns:
            Complete response with answer, metadata, and performance metrics
        """
        logger.info(
            "Processing user request",
            query=query[:100],
            user_id=user_id,
            session_id=session_id,
            persona=persona,
        )

        try:
            # Process through main ADK agent
            response = await self.coffee_assistant.process_user_request(
                query=query,
                user_id=user_id,
                session_id=session_id,
            )

            # Add persona information to metadata
            response["metadata"]["persona"] = persona

            logger.info(
                "Request processed successfully",
                response_time_ms=response["response_time_ms"],
                agent_used=response["agent_used"],
                intent=response["intent"]["intent"],
                confidence=response["intent"]["confidence"],
            )

        except Exception as e:
            logger.exception(
                "Request processing failed",
                error=str(e),
                query=query[:50],
                user_id=user_id,
            )

            # Return graceful error response
            return {
                "answer": "I apologize, but I'm experiencing some technical difficulties right now. Please try again in a moment, and I'll be happy to help you with your coffee questions.",
                "intent": {"intent": "error", "confidence": 0.0},
                "products_found": 0,
                "agent_used": "ADKOrchestrator",
                "session_id": session_id,
                "response_time_ms": 0,
                "error": str(e),
                "metadata": {
                    "user_id": user_id,
                    "persona": persona,
                    "error_occurred": True,
                    "fallback_response": True,
                },
            }
        else:
            return response

    async def get_agent_status(self) -> dict[str, Any]:
        """Get status information about all agents and tools.

        Returns:
            Status information for monitoring and debugging
        """
        try:
            return {
                "orchestrator_status": "healthy",
                "main_agent": {
                    "name": self.coffee_assistant.agent.name,
                    "model": self.coffee_assistant.agent.model,
                    "tools_count": len(self.coffee_assistant.agent.tools),
                },
                "sub_agents": [
                    {
                        "name": self.coffee_assistant.intent_detector.agent.name,
                        "model": self.coffee_assistant.intent_detector.agent.model,
                        "role": "intent_classification",
                    },
                    {
                        "name": self.coffee_assistant.product_rag_agent.agent.name,
                        "model": self.coffee_assistant.product_rag_agent.agent.model,
                        "role": "product_search",
                    },
                    {
                        "name": self.coffee_assistant.conversation_agent.agent.name,
                        "model": self.coffee_assistant.conversation_agent.agent.model,
                        "role": "general_conversation",
                    },
                ],
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                    }
                    for tool in self.tool_registry.all_tools
                ],
                "services": {
                    "product_service": "connected",
                    "chat_service": "connected",
                    "embedding_service": "connected",
                    "intent_service": "connected",
                    "metrics_service": "connected",
                    "cache_service": "connected",
                },
            }

        except Exception as e:
            logger.exception("Failed to get agent status", error=str(e))

            return {
                "orchestrator_status": "error",
                "error": str(e),
                "services": {
                    "status": "unknown",
                },
            }

    async def warm_up(self) -> dict[str, Any]:
        """Warm up the agent system by pre-loading models and testing connections.

        This can be called during application startup to ensure agents are ready
        to handle requests efficiently.

        Returns:
            Warm-up results and timing information
        """
        logger.info("Starting agent system warm-up")

        try:
            warmup_results = {}

            # Test a simple query to warm up the system
            test_response = await self.process_request(
                query="Hello, can you help me?",
                user_id="warmup_test",
            )

            warmup_results["test_query"] = {
                "status": "success" if "error" not in test_response else "failed",
                "response_time_ms": test_response.get("response_time_ms", 0),
                "agent_used": test_response.get("agent_used"),
            }

            # Get agent status
            status = await self.get_agent_status()
            warmup_results["agent_status"] = status

            logger.info("Agent system warm-up completed", results=warmup_results)

        except Exception as e:
            logger.exception("Agent warm-up failed", error=str(e))

            return {
                "status": "failed",
                "error": str(e),
            }
        else:
            return {
                "status": "completed",
                "results": warmup_results,
            }


def create_orchestrator(
    driver: AsyncDriverAdapterBase,
) -> ADKOrchestrator:
    """Factory function to create ADK orchestrator with all dependencies.

    This function creates all required services and initializes the orchestrator.
    It's designed to be called during application startup.

    Args:
        driver: Database driver for service initialization

    Returns:
        Fully initialized ADK orchestrator
    """
    from app.services.cache import CacheService
    from app.services.chat import ChatService
    from app.services.embedding import EmbeddingService
    from app.services.exemplar import ExemplarService
    from app.services.intent import IntentService
    from app.services.metrics import MetricsService
    from app.services.product import ProductService

    logger.info("Creating ADK orchestrator with services")

    # Initialize all services
    product_service = ProductService(driver)
    chat_service = ChatService(driver)
    embedding_service = EmbeddingService(driver)
    exemplar_service = ExemplarService(driver)
    intent_service = IntentService(driver, exemplar_service, embedding_service)
    metrics_service = MetricsService(driver)
    cache_service = CacheService(driver)

    # Create orchestrator
    orchestrator = ADKOrchestrator(
        product_service=product_service,
        chat_service=chat_service,
        embedding_service=embedding_service,
        intent_service=intent_service,
        metrics_service=metrics_service,
        cache_service=cache_service,
    )

    logger.info("ADK orchestrator created successfully")

    return orchestrator
