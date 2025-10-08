"""Chat-related schemas for UI interaction."""

from datetime import datetime

from app.schemas.base import CamelizedBaseStruct

__all__ = (
    "ChatMessage",
    "ChatMessageRequest",
)


class ChatMessage(CamelizedBaseStruct, omit_defaults=True):
    """Chat message for UI."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime | None = None


class ChatMessageRequest(CamelizedBaseStruct, omit_defaults=True):
    """Chat message request from frontend."""

    message: str
    persona: str = "enthusiast"
