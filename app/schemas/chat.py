"""Chat-related schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import msgspec

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = (
    "ChatConversation",
    "ChatConversationCreate",
    "ChatMessage",
    "ChatMessageRequest",
    "ChatSession",
    "ChatSessionCreate",
)


class ChatSession(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Chat session data schema."""

    id: UUID
    user_id: str | None = None
    session_data: dict[str, Any] | None = None
    last_activity: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatSessionCreate(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Chat session creation schema."""

    user_id: str | None = None
    session_data: dict[str, Any] | None = None


class ChatConversation(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Chat conversation data schema."""

    id: UUID
    session_id: UUID
    role: str  # 'user', 'assistant', or 'system'
    content: str
    metadata: dict[str, Any] | None = None
    intent_classification: dict[str, Any] | None = None
    created_at: datetime | None = None


class ChatConversationCreate(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Chat conversation creation schema."""

    session_id: UUID
    role: str  # 'user', 'assistant', or 'system'
    content: str
    metadata: dict[str, Any] | None = None
    intent_classification: dict[str, Any] | None = None


class ChatMessage(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Chat message for UI."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime | None = None


class ChatMessageRequest(msgspec.Struct, gc=False, omit_defaults=True):
    """Chat message request from frontend."""

    message: str
    persona: str = "enthusiast"
