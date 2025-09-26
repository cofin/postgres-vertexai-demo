"""ADK Agent Orchestrator for Coffee Assistant System.

This module provides the main orchestrator class that manages the ADK agent system
using the proper ADK Runner pattern with our custom session service.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from google.adk import Runner

from app.config import db
from app.services.adk.agent import CoffeeAssistantAgent  # This now imports the router agent
from app.services.adk.session import ChatSessionService

logger = structlog.get_logger()


class ADKOrchestrator:
    """Main orchestrator for the ADK-based coffee assistant system.

    This class uses the proper ADK Runner pattern with our custom session service
    that bridges ADK sessions with our existing chat infrastructure.
    """

    def __init__(self) -> None:
        """Initialize the ADK orchestrator with proper ADK components."""
        self.session_service = ChatSessionService(db_config=db)
        # The 'agent' is now the main router agent from agent.py
        self.runner = Runner(
            agent=CoffeeAssistantAgent,
            app_name="coffee-assistant",
            session_service=self.session_service,
        )
        logger.info("ADK Orchestrator initialized with Multi-Agent Router Pattern")

    async def process_request(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        persona: str = "enthusiast",
    ) -> dict[str, Any]:
        """Process user request through ADK agent system."""
        start_time = time.time()
        logger.info("Processing request via ADK Runner...", query=query)

        try:
            final_response = await self.runner.process(query=query, session_id=session_id)
            total_time_ms = int((time.time() - start_time) * 1000)

            # --- Data Extraction from ADK Response ---
            # NOTE: The structure of 'final_response' is assumed based on typical agent traces.
            # This logic will need to be adapted to the actual object structure.
            agent_used = getattr(final_response, "invoked_agent_name", "ADK Multi-Agent")
            intent_details = {}
            search_details = {}
            products_found = []

            # Hypothetical trace inspection
            if hasattr(final_response, "trace") and final_response.trace:
                for event in final_response.trace:
                    if event.tool_name == "classify_intent":
                        intent_details = event.tool_output
                    if event.tool_name == "search_products_by_vector":
                        products_found = event.tool_output
                        search_details = {
                            "query": event.tool_input.get("query"),
                            "sql": "SELECT name, 1 - (embedding <=> ...) FROM product ...", # Representative SQL
                            "results_count": len(products_found)
                        }

            debug_info = {
                "intent": intent_details,
                "search": search_details,
                "timings": {"total_ms": total_time_ms},
                "agent_used": agent_used,
            }

        except Exception as e:
            logger.exception("Request processing failed", error=str(e), query=query)
            return {
                "answer": "I apologize, but I'm experiencing some technical difficulties.",
                "intent": {"intent": "error"},
                "products": [],
                "agent_used": "ErrorFallback",
                "session_id": session_id,
                "response_time_ms": int((time.time() - start_time) * 1000),
                "error": str(e),
                "metadata": {"user_id": user_id, "persona": persona, "error_occurred": True},
            }
        else:
            return {
                "answer": final_response.text,
                "products": products_found,
                "agent_used": agent_used,
                "session_id": session_id,
                "response_time_ms": total_time_ms,
                "debug_info": debug_info, # Pass rich context to the controller
                "metadata": {
                    "user_id": user_id,
                    "persona": persona,
                },
            }
