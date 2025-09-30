"""ADK Agent Orchestrator for Coffee Assistant System.

This module provides the main orchestrator class that manages the ADK agent system
using the proper ADK Runner pattern with our custom session service.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from app.schemas.chat import ChatSession

import structlog
from google.adk import Runner
from google.genai import errors, types

from app.config import db, service_locator, sqlspec
from app.services.adk.agent import CoffeeAssistantAgent  # This now imports the router agent
from app.services.adk.session import ChatSessionService
from app.services.adk.tools import get_and_clear_timing_context
from app.services.cache import CacheService
from app.services.metrics import MetricsService

logger = structlog.get_logger()

# HTTP Status codes
HTTP_SERVICE_UNAVAILABLE = 503


class ADKOrchestrator:
    """Main orchestrator for the ADK-based coffee assistant system.

    This class uses the proper ADK Runner pattern with our custom session service
    that bridges ADK sessions with our existing chat infrastructure.
    """

    def __init__(self) -> None:
        """Initialize the ADK orchestrator with proper ADK components."""
        self.session_service = ChatSessionService(db_config=db)
        self.runner = Runner(
            agent=CoffeeAssistantAgent,
            app_name="coffee-assistant",
            session_service=self.session_service,
        )
        logger.debug("ADK Orchestrator initialized with an Agent Pattern")

    def _convert_markdown_to_html(self, text: str) -> str:
        """Convert simple markdown formatting to HTML."""
        if not text:
            return text

        # Convert **bold** to <strong>bold</strong>
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

        # Convert *italic* to <em>italic</em>
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

        # Convert numbered lists (1. item) to proper format
        lines = text.split("\n")
        in_list = False
        result_lines = []

        for line in lines:
            stripped = line.strip()
            if re.match(r"^\d+\.\s+", stripped):
                if not in_list:
                    result_lines.append("")  # Add space before list
                    in_list = True
                # Remove number and just keep the content
                item_text = re.sub(r"^\d+\.\s+", "", stripped)
                result_lines.append(item_text)
            else:
                if in_list and stripped:
                    in_list = False
                    result_lines.append("")  # Add space after list
                result_lines.append(line)

        return "\n".join(result_lines)

    async def process_request(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        persona: str = "enthusiast",
    ) -> dict[str, Any]:
        """Process user request through ADK agent system with detailed timing."""
        start_time = time.time()
        timings = {}
        logger.debug("Processing request via ADK Runner...", query=query)

        try:
            # Time session management
            session_start = time.time()
            session = await self._ensure_session(user_id, session_id)
            timings["session_ms"] = round((time.time() - session_start) * 1000, 2)

            # Initialize cache variables
            from_cache = False
            event_data = None

            # Check cache first using database session
            cache_key = f"adk_response:{hash(query)}:{persona}"
            async with sqlspec.provide_session(db) as cache_session:
                cache_service = service_locator.get(CacheService, cache_session)
                cached_response = await cache_service.get(cache_key)
                from_cache = cached_response is not None

                if cached_response:
                    logger.debug("Using cached response", cache_key=cache_key)
                    event_data = cached_response
                    timings["agent_processing_ms"] = 0  # No processing time for cached responses
                else:
                    # Time ADK agent processing
                    agent_start = time.time()
                    try:
                        events = await self._run_agent(query, user_id, session.id)
                        event_data = await self._process_events(events, query, timings)
                    except errors.ServerError as e:
                        # If all retries failed, return a graceful fallback
                        if e.status_code == HTTP_SERVICE_UNAVAILABLE:
                            logger.exception("ADK service unavailable after retries")
                            event_data = {
                                "final_response_text": "I apologize, but I'm experiencing some technical difficulties connecting to the AI service. Please try again in a moment.",
                                "agent_used": "Fallback",
                                "intent_details": {"intent": "GENERAL_CONVERSATION", "confidence": 0.0},
                                "search_details": {},
                                "products_found": [],
                            }
                        else:
                            raise
                    timings["agent_processing_ms"] = round((time.time() - agent_start) * 1000, 2)

                    # Cache the response
                    await cache_service.set(cache_key, event_data, ttl=5)  # 5-minute TTL
                    logger.debug("Cached response", cache_key=cache_key)

            # Get timing data from tool context
            tool_timings = get_and_clear_timing_context()
            if "intent_classification" in tool_timings:
                timings["intent_classification_ms"] = tool_timings["intent_classification"]["timing_ms"]
                # Update intent details with SQL query
                if event_data["intent_details"]:
                    event_data["intent_details"]["sql_query"] = tool_timings["intent_classification"]["sql_query"]
            if "vector_search" in tool_timings:
                timings["vector_search_ms"] = tool_timings["vector_search"]["total_ms"]
                timings["embedding_generation_ms"] = tool_timings["vector_search"]["embedding_ms"]
                timings["embedding_cache_hit"] = tool_timings["vector_search"]["embedding_cache_hit"]
                # Update search details with actual data from tools
                event_data["search_details"].update({
                    "sql": tool_timings["vector_search"]["sql_query"],
                    "params": tool_timings["vector_search"]["params"],
                    "results_count": tool_timings["vector_search"]["results_count"],
                })

            total_time_ms = round((time.time() - start_time) * 1000, 2)
            timings["total_ms"] = total_time_ms

            debug_info = self._build_debug_info(event_data, timings, from_cache)

            # Record metrics with all timing components
            await self._record_metrics(session.id, query, event_data, timings)

            return self._build_success_response(
                event_data, session.id, total_time_ms, debug_info, user_id, persona, from_cache
            )

        except Exception as e:
            logger.exception("Request processing failed", error=str(e), query=query)
            return self._build_error_response(e, session_id, start_time, user_id, persona)

    async def _ensure_session(self, user_id: str, session_id: str | None) -> ChatSession:
        """Ensure session exists using upsert pattern."""
        return await self.session_service.upsert_session(
            app_name="coffee-assistant",
            user_id=user_id,
            session_id=session_id,
            state={},
        )

    async def _run_agent(self, query: str, user_id: str, session_id: str) -> AsyncGenerator:
        """Run the ADK agent with the user query with retry logic."""
        content = types.Content(role="user", parts=[types.Part(text=query)])

        # Retry logic for transient errors
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                return self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                )
            except errors.ServerError as e:
                # Check if it's a timeout or other retryable error
                if e.status_code == HTTP_SERVICE_UNAVAILABLE and attempt < max_retries - 1:
                    logger.warning(
                        "ADK request timed out, retrying...",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Last attempt or non-retryable error
                    raise
            except Exception:
                # Non-server errors should not be retried
                raise
        return None

    async def _process_events(self, events: AsyncGenerator, query: str, timings: dict) -> dict[str, Any]:
        """Process ADK events and extract relevant information with timing."""
        final_response_text = ""
        agent_used = "ADK Multi-Agent"
        intent_details = {}
        search_details = {}
        products_found = []

        async for event in events:
            # Only process final responses for the actual answer
            if event.is_final_response() and event.content and event.content.parts:
                # Extract only text parts, ignoring function calls and other non-text content
                text_parts = [part.text for part in event.content.parts if hasattr(part, "text") and part.text]

                # Only set final response if we have actual text content
                if text_parts:
                    final_response_text = self._convert_markdown_to_html("".join(text_parts))
                    agent_used = event.author or "ADK Multi-Agent"

            function_responses = event.get_function_responses()
            if function_responses:
                for func_response in function_responses:
                    if func_response.name == "classify_intent":
                        intent_result = func_response.response or {}
                        # Extract timing if available from tool response
                        if "timing_ms" in intent_result:
                            timings["intent_classification_ms"] = intent_result["timing_ms"]

                        intent_details = {
                            "intent": intent_result.get("intent"),
                            "confidence": intent_result.get("confidence"),
                            "exemplar_used": intent_result.get("exemplar_phrase"),
                        }

                    elif func_response.name == "search_products_by_vector":
                        products_found = func_response.response or []

                        # For backwards compatibility, check if we got timing data
                        # If not, we'll use the hardcoded approach
                        search_details = {
                            "query": query,
                            "sql": """SELECT p.id, p.name, p.description, p.price,
       1 - (p.embedding <=> %s) as similarity
FROM product p
WHERE 1 - (p.embedding <=> %s) > %s
ORDER BY similarity DESC
LIMIT %s""",
                            "params": {
                                "similarity_threshold": 0.7,
                                "limit": len(products_found) if isinstance(products_found, list) else 0,
                            },
                            "results_count": len(products_found) if isinstance(products_found, list) else 0,
                        }

        return {
            "final_response_text": final_response_text,
            "agent_used": agent_used,
            "intent_details": intent_details,
            "search_details": search_details,
            "products_found": products_found,
        }

    def _build_debug_info(self, event_data: dict[str, Any], timings: dict, from_cache: bool = False) -> dict[str, Any]:
        """Build debug information with detailed timing breakdown."""
        return {
            "intent": event_data["intent_details"],
            "search": event_data["search_details"],
            "timings": {
                "total_ms": timings.get("total_ms", 0),
                "agent_processing_ms": timings.get("agent_processing_ms", 0),
                "session_ms": timings.get("session_ms", 0),
                "intent_classification_ms": timings.get("intent_classification_ms", 0),
                "vector_search_ms": timings.get("vector_search_ms", 0),
                "embedding_generation_ms": timings.get("embedding_generation_ms", 0),
                "embedding_cache_hit": timings.get("embedding_cache_hit", False),
            },
            "agent_used": event_data["agent_used"],
            "from_cache": from_cache,
        }

    async def _record_metrics(self, session_id: str, query: str, event_data: dict, timings: dict) -> None:
        """Record detailed metrics."""
        try:
            async with sqlspec.provide_session(db) as session:
                metrics_service = service_locator.get(MetricsService, session)
                # Calculate average similarity score from products
                products = event_data.get("products_found", [])
                avg_similarity = 0.0
                if products:
                    similarity_scores = [
                        product["similarity_score"]
                        for product in products
                        if isinstance(product, dict) and "similarity_score" in product
                    ]

                    if similarity_scores:
                        avg_similarity = sum(similarity_scores) / len(similarity_scores)

                await metrics_service.record_search_metric(
                    session_id=session_id,
                    query_text=query,
                    intent=event_data.get("intent_details", {}).get("intent"),
                    confidence_score=event_data.get("intent_details", {}).get("confidence"),
                    vector_search_results=len(event_data.get("products_found", [])),
                    total_response_time_ms=int(timings.get("total_ms", 0)),  # Store as int in DB
                    vector_search_time_ms=int(timings.get("vector_search_ms", 0))
                    if timings.get("vector_search_ms")
                    else None,
                    llm_response_time_ms=int(timings.get("agent_processing_ms", 0))
                    if timings.get("agent_processing_ms")
                    else None,
                    embedding_cache_hit=timings.get("embedding_cache_hit", False),
                    intent_exemplar_used=event_data.get("intent_details", {}).get("exemplar_used"),
                    avg_similarity_score=avg_similarity,
                )
        except Exception:
            logger.exception("Failed to record metrics")

    def _build_success_response(
        self,
        event_data: dict[str, Any],
        session_id: str,
        total_time_ms: float,
        debug_info: dict[str, Any],
        user_id: str,
        persona: str,
        from_cache: bool = False,
    ) -> dict[str, Any]:
        """Build successful response dictionary."""
        return {
            "answer": event_data["final_response_text"],
            "products": event_data["products_found"],
            "agent_used": event_data["agent_used"],
            "session_id": session_id,
            "response_time_ms": total_time_ms,
            "debug_info": debug_info,
            "from_cache": from_cache,
            "metadata": {
                "user_id": user_id,
                "persona": persona,
            },
        }

    def _build_error_response(
        self,
        error: Exception,
        session_id: str | None,
        start_time: float,
        user_id: str,
        persona: str,
    ) -> dict[str, Any]:
        """Build error response dictionary."""
        return {
            "answer": "I apologize, but I'm experiencing some technical difficulties.",
            "intent": {"intent": "error"},
            "products": [],
            "agent_used": "ErrorFallback",
            "session_id": session_id,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "error": str(error),
            "metadata": {"user_id": user_id, "persona": persona, "error_occurred": True},
        }
