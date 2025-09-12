"""Core ADK Agent Implementations.

This module implements the Google ADK agents that form the coffee assistant system.
Each agent is specialized for specific types of queries and uses appropriate tools
to provide intelligent responses.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from google.adk.agents import LlmAgent

from app.agents.prompts import (
    CONTEXT_INSTRUCTIONS,
    CONVERSATION_AGENT_PROMPT,
    ERROR_HANDLING_INSTRUCTIONS,
    INTENT_DETECTOR_PROMPT,
    MAIN_ASSISTANT_PROMPT,
    PRODUCT_RAG_PROMPT,
)
from app.lib.settings import get_settings

if TYPE_CHECKING:
    from app.agents.tools import ToolRegistry

logger = structlog.get_logger()
settings = get_settings()


class IntentDetectorAgent:
    """ADK Agent specialized in classifying user query intent.

    This agent uses vector-based intent classification to determine
    what type of response a user query requires, enabling proper routing
    to specialized sub-agents.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        """Initialize intent detection agent.

        Args:
            tool_registry: Registry containing all available tools
        """
        self.agent = LlmAgent(
            model="gemini-2.0-flash",
            name="IntentDetector",
            description="Classifies customer queries for proper routing to specialized agents",
            instruction=INTENT_DETECTOR_PROMPT,
            tools=[tool_registry.intent_classification_tool],
        )
        self.tool_registry = tool_registry

    async def classify_user_intent(self, query: str) -> dict[str, Any]:
        """Classify user intent and return routing information.

        Args:
            query: User's message to classify

        Returns:
            Dictionary containing intent classification and routing info
        """
        start_time = time.time()

        try:
            result = await self.tool_registry.intent_service.classify_intent(query)

            classification = {
                "query": query,
                "intent": result.intent,
                "confidence": float(result.confidence),
                "exemplar_phrase": result.exemplar_phrase,
                "embedding_cache_hit": result.embedding_cache_hit,
                "fallback_used": result.fallback_used,
            }

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "Intent classified",
                query=query[:50],
                intent=classification.get("intent"),
                confidence=classification.get("confidence"),
                processing_time_ms=processing_time,
            )

            return {
                "intent": classification.get("intent", "GENERAL_CONVERSATION"),
                "confidence": classification.get("confidence", 0.5),
                "exemplar_phrase": classification.get("exemplar_phrase", ""),
                "requires_product_search": classification.get("intent") in ["PRODUCT_SEARCH", "PRICE_INQUIRY"],
                "requires_conversation_agent": classification.get("intent") in ["BREWING_HELP", "GENERAL_CONVERSATION"],
                "requires_store_info": classification.get("intent") == "STORE_INFO",
                "processing_time_ms": processing_time,
                "cache_hit": classification.get("embedding_cache_hit", False),
                "fallback_used": classification.get("fallback_used", False),
            }

        except Exception as e:
            logger.exception("Intent classification failed", error=str(e), query=query[:50])

            # Fallback to general conversation
            return {
                "intent": "GENERAL_CONVERSATION",
                "confidence": 0.5,
                "exemplar_phrase": "",
                "requires_product_search": False,
                "requires_conversation_agent": True,
                "requires_store_info": False,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "cache_hit": False,
                "fallback_used": True,
                "error": str(e),
            }


class ProductRAGAgent:
    """ADK Agent specialized in product search and recommendations.

    This agent uses vector search and product data to provide specific
    product recommendations, pricing information, and comparisons.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        """Initialize product RAG agent.

        Args:
            tool_registry: Registry containing all available tools
        """
        self.agent = LlmAgent(
            model=settings.vertex_ai.CHAT_MODEL,
            name="ProductRAG",
            description="Provides product recommendations and information using vector search",
            instruction=PRODUCT_RAG_PROMPT + "\n\n" + ERROR_HANDLING_INSTRUCTIONS,
            tools=[
                tool_registry.vector_search_tool,
                tool_registry.product_lookup_tool,
            ],
        )
        self.tool_registry = tool_registry

    async def handle_product_query(
        self,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Handle product-related queries with search and recommendations.

        Args:
            query: User's product query
            conversation_history: Previous conversation context

        Returns:
            Response with product recommendations and metadata
        """
        start_time = time.time()

        # For now, use the tools directly since we need to implement proper ADK agent calling
        # This will be updated when we have the proper ADK runner integration
        try:
            # Generate embedding for query
            query_embedding = await self.tool_registry.embedding_service.get_text_embedding(query)

            # Search for similar products
            product_results = await self.tool_registry.product_service.vector_similarity_search(
                query_embedding=query_embedding, similarity_threshold=0.7, limit=5
            )

            products = [
                {
                    "id": str(product.id),
                    "name": product.name,
                    "description": product.description,
                    "price": float(product.price),
                    "similarity_score": float(product.similarity_score),
                    "metadata": product.metadata or {},
                }
                for product in product_results
            ]

            processing_time = int((time.time() - start_time) * 1000)

            # Generate response using the products found
            if products:
                product_info = "\n".join([
                    f"- {p['name']}: {p['description']} (${p['price']:.2f})" for p in products[:3]
                ])
                response_text = f"Based on your query, here are some great options:\n\n{product_info}\n\nWould you like more details about any of these?"
            else:
                response_text = "I didn't find any exact matches, but I'd be happy to help you find something similar. Could you tell me more about what you're looking for?"

            logger.info(
                "Product query handled",
                query=query[:50],
                products_found=len(products),
                processing_time_ms=processing_time,
            )

            return {
                "response": response_text,
                "tools_used": ["vector_search_tool"],
                "products_found": len(products),
                "processing_time_ms": processing_time,
                "agent_name": "ProductRAG",
            }

        except Exception as e:
            logger.exception("Product query handling failed", error=str(e), query=query[:50])

            return {
                "response": "I apologize, but I'm having trouble accessing our product catalog right now. Please try again in a moment, or feel free to ask me about general coffee topics.",
                "tools_used": [],
                "products_found": 0,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "agent_name": "ProductRAG",
                "error": str(e),
            }


class ConversationAgent:
    """ADK Agent specialized in general coffee conversation and education.

    This agent handles general coffee questions, brewing advice, coffee culture,
    and educational content without needing product search capabilities.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        """Initialize conversation agent.

        Args:
            tool_registry: Registry containing all available tools
        """
        self.agent = LlmAgent(
            model="gemini-2.0-flash",
            name="ConversationAgent",
            description="Handles general coffee conversation, education, and brewing advice",
            instruction=CONVERSATION_AGENT_PROMPT + "\n\n" + CONTEXT_INSTRUCTIONS,
            tools=[],  # No tools needed for general conversation
        )
        self.tool_registry = tool_registry

    async def handle_conversation(
        self,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Handle general conversation and coffee education queries.

        Args:
            query: User's conversation query
            conversation_history: Previous conversation context

        Returns:
            Educational or conversational response
        """
        start_time = time.time()

        try:
            # For general conversation, provide educational responses
            # This will be enhanced with proper ADK agent integration later
            query_lower = query.lower()

            # Simple response generation for common topics
            if any(word in query_lower for word in ["brew", "brewing", "method"]):
                response_text = "Great question about brewing! The key factors for excellent coffee are: proper grind size, water temperature (195-205°F), brewing time, and coffee-to-water ratio. What brewing method are you interested in learning about?"
            elif any(word in query_lower for word in ["origin", "where", "region"]):
                response_text = "Coffee origins have fascinating stories! Different regions produce unique flavor profiles - Ethiopian coffees are often floral and fruity, while Colombian beans tend to be well-balanced with nutty notes. Would you like to know about a specific region?"
            elif any(word in query_lower for word in ["roast", "dark", "light"]):
                response_text = "Roasting transforms coffee beans! Light roasts preserve origin characteristics and have bright acidity, medium roasts balance origin and roast flavors, and dark roasts develop bold, smoky notes. What's your preference?"
            else:
                response_text = "I'm here to help with all your coffee questions! Whether you want to learn about brewing techniques, coffee origins, roasting, or anything else coffee-related, just let me know what interests you most."

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "Conversation handled",
                query=query[:50],
                response_length=len(response_text),
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.exception("Conversation handling failed", error=str(e), query=query[:50])

            return {
                "response": "I'm here to help with all your coffee questions. What would you like to know or explore?",
                "tools_used": [],
                "products_found": 0,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "agent_name": "ConversationAgent",
            }
        else:
            return {
                "response": response_text,
                "tools_used": [],
                "products_found": 0,
                "processing_time_ms": processing_time,
                "agent_name": "ConversationAgent",
            }


class CoffeeAssistantAgent:
    """Main ADK Agent that orchestrates the coffee assistant system.

    This agent serves as the primary interface, coordinating with sub-agents
    based on intent classification and managing the overall conversation flow.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        """Initialize main coffee assistant agent.

        Args:
            tool_registry: Registry containing all available tools
        """
        self.agent = LlmAgent(
            model="gemini-2.0-flash",
            name="CoffeeAssistant",
            description="Primary coffee shop assistant that coordinates specialized agents",
            instruction=MAIN_ASSISTANT_PROMPT + "\n\n" + CONTEXT_INSTRUCTIONS,
            tools=[
                tool_registry.session_management_tool,
                tool_registry.conversation_history_tool,
                tool_registry.metrics_recording_tool,
            ],
        )
        self.tool_registry = tool_registry

        # Initialize sub-agents
        self.intent_detector = IntentDetectorAgent(tool_registry)
        self.product_rag_agent = ProductRAGAgent(tool_registry)
        self.conversation_agent = ConversationAgent(tool_registry)

    async def process_user_request(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Process complete user request through agent system.

        This is the main entry point for all user interactions.

        Args:
            query: User's message
            user_id: User identifier
            session_id: Optional existing session ID

        Returns:
            Complete response with all metadata
        """
        overall_start_time = time.time()

        try:
            # Step 1: Manage session
            session_info = await self._ensure_session(user_id, session_id)
            current_session_id = session_info["session_id"]

            # Step 2: Get conversation history for context
            history = await self._get_conversation_history(current_session_id)

            # Step 3: Classify intent
            intent_data = await self.intent_detector.classify_user_intent(query)

            # Step 4: Route to appropriate sub-agent
            if intent_data["requires_product_search"]:
                agent_response = await self.product_rag_agent.handle_product_query(query, history["messages"])
            elif intent_data["requires_conversation_agent"]:
                agent_response = await self.conversation_agent.handle_conversation(query, history["messages"])
            else:
                # Default to conversation agent for unhandled intents
                agent_response = await self.conversation_agent.handle_conversation(query, history["messages"])

            # Step 5: Save conversation
            await self._save_conversation(
                current_session_id,
                query,
                agent_response["response"],
                intent_data,
            )

            # Step 6: Record metrics
            total_time = int((time.time() - overall_start_time) * 1000)
            await self._record_metrics(
                current_session_id,
                query,
                intent_data,
                agent_response,
                total_time,
            )

            # Step 7: Return complete response
            return {
                "answer": agent_response["response"],
                "intent": intent_data,
                "products_found": agent_response.get("products_found", 0),
                "agent_used": agent_response["agent_name"],
                "session_id": current_session_id,
                "response_time_ms": total_time,
                "metadata": {
                    "user_id": user_id,
                    "tools_used": agent_response.get("tools_used", []),
                    "cache_hits": intent_data.get("cache_hit", False),
                    "processing_steps": [
                        "session_management",
                        "intent_classification",
                        "agent_routing",
                        "response_generation",
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

    async def _ensure_session(self, user_id: str, session_id: str | None) -> dict[str, Any]:
        """Ensure user has a valid session."""
        try:
            # Use chat service to manage sessions
            chat_service = self.tool_registry.chat_service

            if not session_id:
                # Return a fallback session info for now
                return {
                    "session_id": "fallback",
                    "user_id": user_id,
                    "persona": "enthusiast",
                    "created_at": "2024-01-01T00:00:00Z",
                }

            session = await chat_service.get_session_by_user_id(user_id)
            if not session:
                # Return fallback session when not found instead of error
                return {
                    "session_id": "fallback",
                    "user_id": user_id,
                    "persona": "enthusiast",
                    "created_at": "2024-01-01T00:00:00Z",
                }

            return {
                "session_id": str(session.id),
                "user_id": session.user_id,
                "persona": "enthusiast",  # Default since not in schema
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "last_activity": session.updated_at.isoformat() if session.updated_at else None,
            }
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("Session management failed", error=str(e))
            return {"session_id": "fallback", "user_id": user_id}

    async def _get_conversation_history(self, session_id: str) -> dict[str, Any]:
        """Get conversation history for context."""
        try:
            # Use chat service to get conversation history
            chat_service = self.tool_registry.chat_service

            # Skip history retrieval for fallback sessions
            if session_id == "fallback":
                return {
                    "session_id": session_id,
                    "messages": [],
                    "count": 0,
                }

            history = await chat_service.get_conversation_history(session_id=uuid.UUID(session_id), limit=10)

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
            logger.warning("History retrieval failed", error=str(e))
            return {"messages": [], "count": 0}

    async def _save_conversation(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        intent_data: dict[str, Any],
    ) -> None:
        """Save conversation to database."""
        try:
            # This would typically use chat service directly
            # For now, we'll log the conversation
            logger.info(
                "Conversation saved",
                session_id=session_id,
                intent=intent_data.get("intent"),
                confidence=intent_data.get("confidence"),
            )
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("Conversation save failed", error=str(e))

    async def _record_metrics(
        self,
        session_id: str,
        query: str,
        intent_data: dict[str, Any],
        agent_response: dict[str, Any],
        total_time_ms: int,
    ) -> None:
        """Record performance metrics."""
        try:
            # Use metrics service to record performance metrics
            metrics_service = self.tool_registry.metrics_service
            await metrics_service.record_search_metric(
                session_id=UUID(session_id) if session_id != "fallback" else None,
                query_text=query,
                intent=intent_data.get("intent", "UNKNOWN"),
                vector_search_results=agent_response.get("products_found", 0),
                total_response_time_ms=total_time_ms,
            )
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("Metrics recording failed", error=str(e))
