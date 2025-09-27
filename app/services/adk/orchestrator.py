"""ADK Agent Orchestrator for Coffee Assistant System.

This module provides the main orchestrator class that manages the ADK agent system
using the proper ADK Runner pattern with our custom session service.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from google.adk import Runner
from google.genai import types

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
            # Ensure session exists using upsert pattern - create if it doesn't exist
            await self.session_service.upsert_session(
                app_name="coffee-assistant",
                user_id=user_id,
                session_id=session_id,
                state={}
            )

            # Create content object from user query
            content = types.Content(role='user', parts=[types.Part(text=query)])

            # Run the agent asynchronously with proper ADK API
            events = self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            )

            # Process events and extract final response
            final_response_text = ""
            agent_used = "ADK Multi-Agent"
            intent_details = {}
            search_details = {}
            products_found = []

            async for event in events:
                # Look for final response
                if event.is_final_response():
                    if event.content and event.content.parts:
                        final_response_text = event.content.parts[0].text
                        agent_used = event.author or "ADK Multi-Agent"

                # Extract tool-related information if available
                function_calls = event.get_function_calls()
                if function_calls:
                    for func_call in function_calls:
                        if func_call.name == "classify_intent":
                            # Intent classification tool output will be in subsequent events
                            pass
                        elif func_call.name == "search_products_by_vector":
                            # Vector search tool output will be in subsequent events
                            pass

                function_responses = event.get_function_responses()
                if function_responses:
                    for func_response in function_responses:
                        if func_response.name == "classify_intent":
                            intent_details = func_response.response or {}
                        elif func_response.name == "search_products_by_vector":
                            products_found = func_response.response or []
                            search_details = {
                                "query": query,
                                "sql": "SELECT name, 1 - (embedding <=> ...) FROM product ...",
                                "results_count": len(products_found) if isinstance(products_found, list) else 0
                            }

            total_time_ms = int((time.time() - start_time) * 1000)

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
                "answer": final_response_text,
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
