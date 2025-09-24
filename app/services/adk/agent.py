"""Core ADK Agent Implementations.

This module implements the Google ADK agents that form the coffee assistant system.
Each agent now uses fresh database sessions per request to avoid connection issues.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from google.adk.agents import LlmAgent

from app.services.adk.prompts import (
    CONTEXT_INSTRUCTIONS,
    MAIN_ASSISTANT_PROMPT,
)

logger = structlog.get_logger()


class CoffeeAssistantAgent:
    """Main ADK Agent that orchestrates the coffee assistant system.

    This agent serves as the primary interface, using fresh tools and creating
    subagents per request to avoid stale database connections.
    """

    def __init__(self) -> None:
        """Initialize main coffee assistant agent without stored dependencies."""
        from app.services.adk.tools import ALL_TOOLS

        self.agent = LlmAgent(
            model="gemini-2.0-flash",
            name="CoffeeAssistant",
            description="Primary coffee shop assistant with fresh session management",
            instruction=MAIN_ASSISTANT_PROMPT + "\n\n" + CONTEXT_INSTRUCTIONS,
            tools=ALL_TOOLS,  # Use the new tool functions directly
        )

    async def process_user_request(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Process complete user request using new tool functions.

        This method uses the fresh tool functions that get their own database
        sessions rather than stored subagents with stale connections.

        Args:
            query: User's message
            user_id: User identifier
            session_id: Optional existing session ID

        Returns:
            Complete response with all metadata
        """
        import uuid

        from app.services.adk.tools import (
            classify_intent,
            record_search_metric,
            search_products_by_vector,
        )

        overall_start_time = time.time()

        try:
            # Ensure we have a session ID
            if session_id is None:
                session_id = str(uuid.uuid4())

            # Step 1: Classify intent using fresh tool
            intent_data = await classify_intent(query)

            # Step 2: Route based on intent
            if intent_data["intent"] in ["PRODUCT_SEARCH", "PRICE_INQUIRY"]:
                # Product search flow
                products = await search_products_by_vector(query, limit=5)

                if products:
                    max_products_to_show = 3
                    response_text = f"I found {len(products)} coffee products that match your query:\n\n"
                    for product in products[:max_products_to_show]:  # Show top 3
                        response_text += f"• **{product['name']}** - ${product['price']:.2f}\n"
                        response_text += f"  {product['description'][:100]}...\n\n"

                    if len(products) > max_products_to_show:
                        response_text += f"And {len(products) - max_products_to_show} more options available!"
                else:
                    response_text = "I couldn't find any products matching your query. Could you try describing what you're looking for differently?"

                products_found = len(products)
                agent_used = "ProductSearchAgent"

            else:
                # General conversation flow
                query_lower = query.lower()
                if any(word in query_lower for word in ["brew", "brewing", "method"]):
                    response_text = "Great question about brewing! The key factors for excellent coffee are: proper grind size, water temperature (195-205°F), brewing time, and coffee-to-water ratio. What brewing method are you interested in learning about?"
                elif any(word in query_lower for word in ["origin", "where", "region"]):
                    response_text = "Coffee origins have fascinating stories! Different regions produce unique flavor profiles - Ethiopian coffees are often floral and fruity, while Colombian beans tend to be well-balanced with nutty notes. Would you like to know about a specific region?"
                elif any(word in query_lower for word in ["roast", "dark", "light"]):
                    response_text = "Roasting transforms coffee beans! Light roasts preserve origin characteristics and have bright acidity, medium roasts balance origin and roast flavors, and dark roasts develop bold, smoky notes. What's your preference?"
                else:
                    response_text = "I'm here to help with all your coffee questions! Whether you want to learn about brewing techniques, coffee origins, roasting, or find specific products, just let me know what interests you most."

                products_found = 0
                agent_used = "ConversationAgent"

            # Step 3: Record metrics
            total_time = int((time.time() - overall_start_time) * 1000)
            await record_search_metric(
                session_id=session_id,
                query_text=query,
                intent=intent_data["intent"],
                response_time_ms=total_time,
                vector_results=products_found,
                agent_used=agent_used,
            )

            # Step 4: Return complete response
            return {
                "answer": response_text,
                "intent": intent_data,
                "products_found": products_found,
                "agent_used": agent_used,
                "session_id": session_id,
                "response_time_ms": total_time,
                "metadata": {
                    "user_id": user_id,
                    "tools_used": ["classify_intent", "search_products_by_vector" if products_found > 0 else "conversation"],
                    "cache_hits": intent_data.get("embedding_cache_hit", False),
                    "processing_steps": [
                        "intent_classification",
                        "response_generation",
                        "metrics_recording",
                    ],
                },
            }

        except Exception as e:
            logger.exception("Main agent processing failed", error=str(e), query=query[:50])

            total_time = int((time.time() - overall_start_time) * 1000)

            return {
                "answer": "I apologize, but I'm experiencing some technical difficulties. Please try again, and I'll do my best to help you.",
                "intent": {"intent": "error", "confidence": 0.0},
                "products_found": 0,
                "agent_used": "CoffeeAssistant",
                "session_id": session_id,
                "response_time_ms": total_time,
                "error": str(e),
                "metadata": {
                    "user_id": user_id,
                    "error_occurred": True,
                },
            }
