"""Multimodal chat message schemas.

Supports text, image, audio, and mixed content types with metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal


class ContentType(str, Enum):
    """Content types for chat messages."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    MIXED = "mixed"


@dataclass
class MessageMetadata:
    """Metadata for chat messages."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    intent: str | None = None
    confidence: float | None = None
    response_time_ms: int | None = None
    from_cache: bool = False
    embedding_cache_hit: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultimodalContent:
    """Content item within a message."""

    type: ContentType
    text: str | None = None
    image_url: str | None = None
    audio_url: str | None = None
    mime_type: str | None = None


@dataclass
class MultimodalMessage:
    """Chat message supporting multiple content types.

    Replaces simple text messages with rich multimodal support.
    """

    id: str
    role: Literal["user", "assistant"]
    content: list[MultimodalContent] = field(default_factory=list)
    metadata: MessageMetadata = field(default_factory=MessageMetadata)
    session_id: str | None = None

    @property
    def text_content(self) -> str:
        """Extract all text content from message."""
        texts = [c.text for c in self.content if c.type == ContentType.TEXT and c.text]
        return " ".join(texts)

    def to_json(self) -> dict[str, Any]:
        """Serialize to JSON."""
        return {
            "id": self.id,
            "role": self.role,
            "content": [
                {
                    "type": c.type.value,
                    "text": c.text,
                    "image_url": c.image_url,
                    "audio_url": c.audio_url,
                    "mime_type": c.mime_type,
                }
                for c in self.content
            ],
            "metadata": {
                "timestamp": self.metadata.timestamp.isoformat(),
                "intent": self.metadata.intent,
                "confidence": self.metadata.confidence,
                "response_time_ms": self.metadata.response_time_ms,
                "from_cache": self.metadata.from_cache,
                "embedding_cache_hit": self.metadata.embedding_cache_hit,
            },
            "session_id": self.session_id,
        }
