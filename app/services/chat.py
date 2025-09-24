"""Chat service for managing chat sessions and conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql

from app.schemas import (
    ChatConversation,
    ChatMessage,
    ChatSession,
)
from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from uuid import UUID


class ChatService(SQLSpecService):
    """Handles database operations for chat sessions and conversations."""


    async def get_session_by_session_id(self, session_id: UUID) -> ChatSession:
        """Get a chat session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session data

        Raises:
            ValueError: If session not found
        """
        return await self.get_or_404(
            sql.select("id", "user_id", "session_data", "last_activity", "expires_at", "created_at", "updated_at")
            .from_("chat_session")
            .where_eq("id", session_id),
            schema_type=ChatSession,
            error_message=f"Session {session_id} not found",
        )

    async def get_session_by_user_id(self, user_id: str) -> ChatSession | None:
        """Get a chat session by user ID.

        Args:
            user_id: User ID string

        Returns:
            Session data or None if not found
        """
        return await self.driver.select_one_or_none(
            sql.select("id", "user_id", "session_data", "last_activity", "expires_at", "created_at", "updated_at")
            .from_("chat_session")
            .where_eq("user_id", user_id),
            schema_type=ChatSession,
        )





    async def get_conversation_history(self, session_id: UUID, limit: int = 10) -> list[ChatMessage]:
        """Get conversation history as chat messages.

        Args:
            session_id: Session UUID
            limit: Maximum number of conversation pairs

        Returns:
            List of chat messages (user and assistant)
        """
        conversations = await self.driver.select(
            sql.select("id", "session_id", "role", "content", "metadata", "intent_classification", "created_at")
            .from_("chat_conversation")
            .where_eq("session_id", session_id)
            .order_by("created_at DESC")
            .limit(limit),
            schema_type=ChatConversation,
        )

        # Convert to chat messages
        return [
            ChatMessage(
                role=conv.role,
                content=conv.content,
                timestamp=conv.created_at,
            )
            for conv in conversations
        ]


