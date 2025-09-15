"""Chat service for managing chat sessions and conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import sql

from app.config import sqlspec
from app.schemas import (
    ChatConversation,
    ChatConversationCreate,
    ChatMessage,
    ChatSession,
    ChatSessionCreate,
)
from app.services.base import SQLSpecService

if TYPE_CHECKING:
    from uuid import UUID


class ChatService(SQLSpecService):
    """Handles database operations for chat sessions and conversations."""

    async def create_session(self, data: ChatSessionCreate) -> ChatSession:
        """Create a new chat session.

        Args:
            data: Session creation data

        Returns:
            Created session
        """
        session_id = await self.driver.select_value(
            sql.insert("chat_session").columns(
                "user_id", "session_data"
            ).values(
                user_id=data.user_id,
                session_data=data.session_data,
            ).returning("id")
        )

        return await self.get_session(session_id)

    async def get_session(self, session_id: UUID) -> ChatSession:
        """Get a chat session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session data

        Raises:
            ValueError: If session not found
        """
        return await self.get_or_404(
            sql.select(
                "id", "user_id", "session_data", "last_activity", "expires_at", "created_at", "updated_at"
            ).from_("chat_session").where_eq("id", session_id),
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
            sql.select(
                "id", "user_id", "session_data", "last_activity", "expires_at", "created_at", "updated_at"
            ).from_("chat_session").where_eq("user_id", user_id),
            schema_type=ChatSession,
        )

    async def update_session_data(self, session_id: UUID, session_data: dict[str, Any]) -> ChatSession:
        """Update session data.

        Args:
            session_id: Session UUID
            session_data: New session data

        Returns:
            Updated session
        """
        await self.driver.execute(
            sql.update("chat_session")
            .set(session_data=session_data, updated_at=sql.raw("NOW()"))
            .where_eq("id", session_id)
        )

        return await self.get_session(session_id)

    async def add_conversation(self, data: ChatConversationCreate) -> ChatConversation:
        """Add a conversation to a chat session.

        Args:
            data: Conversation data

        Returns:
            Created conversation
        """
        conversation_id = await self.driver.select_value(
            sql.insert("chat_conversation").columns(
                "session_id", "role", "content", "metadata", "intent_classification"
            ).values(
                session_id=data.session_id,
                role=data.role,
                content=data.content,
                metadata=data.metadata,
                intent_classification=data.intent_classification,
            ).returning("id")
        )

        return await self.get_conversation(conversation_id)

    async def get_conversation(self, conversation_id: UUID) -> ChatConversation:
        """Get a conversation by ID.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Conversation data

        Raises:
            ValueError: If conversation not found
        """
        return await self.get_or_404(
            sql.select(
                "id", "session_id", "role", "content", "metadata", "intent_classification", "created_at"
            ).from_("chat_conversation").where_eq("id", conversation_id),
            schema_type=ChatConversation,
            error_message=f"Conversation {conversation_id} not found",
        )

    async def get_session_conversations(self, session_id: UUID, limit: int = 50) -> list[ChatConversation]:
        """Get conversations for a session.

        Args:
            session_id: Session UUID
            limit: Maximum number of conversations

        Returns:
            List of conversations ordered by creation time
        """
        return await self.driver.select(
            sql.select(
                "id", "session_id", "role", "content", "metadata", "intent_classification", "created_at"
            ).from_("chat_conversation").where_eq(
                "session_id", session_id
            ).order_by("created_at").limit(limit),
            schema_type=ChatConversation,
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
            sql.select(
                "id", "session_id", "role", "content", "metadata", "intent_classification", "created_at"
            ).from_("chat_conversation").where_eq(
                "session_id", session_id
            ).order_by("created_at DESC").limit(limit),
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

    async def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old chat sessions.

        Args:
            days_old: Sessions older than this many days will be deleted

        Returns:
            Number of sessions deleted
        """
        result = await self.driver.execute(
            sql.delete("chat_session").where(
                f"created_at < NOW() - INTERVAL '{days_old} days'"
            )
        )
        return result.rowcount if hasattr(result, "rowcount") else 0

    async def get_session_stats(self, session_id: UUID) -> dict[str, Any]:
        """Get statistics for a chat session.

        Args:
            session_id: Session UUID

        Returns:
            Dictionary with session statistics
        """
        stats = await self.driver.select_one_or_none(
            sqlspec.get_sql("get-session-stats"),
            session_id=session_id,
        )

        return stats or {
            "conversation_count": 0,
            "first_message_at": None,
            "last_message_at": None,
        }
