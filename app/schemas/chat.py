"""Chat-related schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.base import CamelizedBaseStruct

__all__ = (
    "ChatConversation",
    "ChatConversationCreate",
    "ChatMessage",
    "ChatMessageRequest",
    "ChatSession",
    "ChatSessionCreate",
)


class ChatSession(CamelizedBaseStruct, omit_defaults=True):
    """Chat session data schema."""

    id: UUID
    user_id: str | None = None
    session_data: dict[str, Any] | None = None
    last_activity: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatSessionCreate(CamelizedBaseStruct, omit_defaults=True):
    """Chat session creation schema."""

    user_id: str | None = None
    session_data: dict[str, Any] | None = None


class ChatConversation(CamelizedBaseStruct, omit_defaults=True):
    """Chat conversation data schema."""

    id: int
    session_id: UUID
    role: str  # 'user', 'assistant', or 'system'
    content: str
    metadata: dict[str, Any] | None = None
    intent_classification: dict[str, Any] | None = None
    created_at: datetime | None = None


class ChatConversationCreate(CamelizedBaseStruct, omit_defaults=True):
    """Chat conversation creation schema."""

    session_id: UUID
    role: str  # 'user', 'assistant', or 'system'
    content: str
    metadata: dict[str, Any] | None = None
    intent_classification: dict[str, Any] | None = None


class ChatMessage(CamelizedBaseStruct, omit_defaults=True):
    """Chat message for UI."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime | None = None


class ChatMessageRequest(CamelizedBaseStruct, omit_defaults=True):
    """Chat message request from frontend."""

    message: str
    persona: str = "enthusiast"
