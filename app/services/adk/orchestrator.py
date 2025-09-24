"""ADK Agent Orchestrator for Coffee Assistant System.

This module provides the main orchestrator class that manages the ADK agent system
using the proper ADK Runner pattern with our custom session service.
"""

from __future__ import annotations

from typing import Any

import structlog
from google.adk import Runner

from app.config import db
from app.services.adk.agent import CoffeeAssistantAgent
from app.services.adk.session import ChatSessionService

logger = structlog.get_logger()


class ADKOrchestrator:
    """Main orchestrator for the ADK-based coffee assistant system.

    This class uses the proper ADK Runner pattern with our custom session service
    that bridges ADK sessions with our existing chat infrastructure.
    """

    def __init__(self) -> None:
        """Initialize the ADK orchestrator with proper ADK components."""
        # Create our custom session service that bridges with chat infrastructure
        self.session_service = ChatSessionService(db_config=db)

        # Create the main coffee assistant agent (no stored dependencies)
        self.agent = CoffeeAssistantAgent()

        # Create ADK Runner with proper session management
        self.runner = Runner(
            agent=self.agent.agent,  # The LlmAgent instance
            app_name="coffee-assistant",
            session_service=self.session_service,
        )

        logger.info(
            "ADK Orchestrator initialized with Runner pattern",
            agent_name=self.agent.agent.name,
            app_name="coffee-assistant",
        )

    async def process_request(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        persona: str = "enthusiast",
    ) -> dict[str, Any]:
        """Process user request through ADK agent system.

        This is the main entry point for all user interactions using the
        proper ADK Runner pattern.

        Args:
            query: User's message or question
            user_id: Unique user identifier
            session_id: Optional existing session ID
            persona: User persona for tailored responses

        Returns:
            Complete response with answer, metadata, and performance metrics
        """
        logger.info(
            "Processing user request via ADK Runner",
            query=query[:100],
            user_id=user_id,
            session_id=session_id,
            persona=persona,
        )

        try:
            # Use our simplified agent processing (it handles its own session management)
            response = await self.agent.process_user_request(
                query=query,
                user_id=user_id,
                session_id=session_id,
            )

            # Add persona information to metadata
            response.setdefault("metadata", {})["persona"] = persona

            logger.info(
                "Request processed successfully via ADK Runner",
                response_time_ms=response["response_time_ms"],
                agent_used=response["agent_used"],
                intent=response["intent"]["intent"],
                confidence=response["intent"]["confidence"],
            )

            return response

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

    async def get_agent_status(self) -> dict[str, Any]:
        """Get status information about the agent runner and services.

        Returns:
            Status information for monitoring and debugging
        """
        try:
            return {
                "orchestrator_status": "healthy",
                "runner": {
                    "agent_name": self.runner.agent.name if self.runner.agent else None,
                    "app_name": "coffee-assistant",
                    "session_service": "ChatSessionService",
                    "type": "adk_runner_pattern",
                },
                "agent": {
                    "name": self.agent.agent.name,
                    "model": "gemini-2.0-flash",
                    "tools_count": len(self.agent.agent.tools) if self.agent.agent.tools else 0,
                },
                "session_service": {
                    "type": "ChatSessionService",
                    "bridges_to": "chat_session_table",
                },
            }

        except Exception as e:
            logger.exception("Failed to get agent status", error=str(e))

            return {
                "orchestrator_status": "error",
                "error": str(e),
                "runner": {
                    "status": "unknown",
                },
            }

    async def warm_up(self) -> dict[str, Any]:
        """Warm up the agent system by testing basic functionality.

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

            return {
                "status": "completed",
                "results": warmup_results,
            }

        except Exception as e:
            logger.exception("Agent warm-up failed", error=str(e))

            return {
                "status": "failed",
                "error": str(e),
            }
