"""Core ADK Agent Implementations.

This module implements the Google ADK agents that form the coffee assistant system.
Each agent now uses fresh database sessions per request to avoid connection issues.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from app.config import settings
from app.services.adk.prompts import (
    CONVERSATION_AGENT_INSTRUCTION,
    PRODUCT_AGENT_INSTRUCTION,
    ROUTER_AGENT_INSTRUCTION,
)
from app.services.adk.tools import (
    classify_intent,
    get_product_details,
    search_products_by_vector,
)

# 1. Define Specialist Sub-Agents
product_agent = LlmAgent(
    name="ProductAgent",
    description="A specialist for finding, recommending, and comparing coffee products available at Cymbal Coffee.",
    instruction=PRODUCT_AGENT_INSTRUCTION,
    model=settings.vertex_ai.CHAT_MODEL,
    tools=[search_products_by_vector, get_product_details],
)

conversation_agent = LlmAgent(
    name="ConversationAgent",
    description="A specialist for discussing general coffee knowledge, brewing techniques, coffee origins, engaging in casual conversation, and making product recommendations when requested.",
    instruction=CONVERSATION_AGENT_INSTRUCTION,
    model=settings.vertex_ai.CHAT_MODEL,
    tools=[search_products_by_vector, get_product_details],
)

# 2. Define the Main Router Agent
CoffeeAssistantAgent = LlmAgent(
    name="CoffeeAssistantRouter",
    description="The main assistant for Cymbal Coffee. It understands a user's request and routes it to the correct specialist agent.",
    instruction=ROUTER_AGENT_INSTRUCTION,
    model=settings.vertex_ai.CHAT_MODEL,
    # Add intent classification tool to router agent
    tools=[classify_intent],
    # The 'sub_agents' parameter is key to the multi-agent architecture.
    sub_agents=[product_agent, conversation_agent],
)
