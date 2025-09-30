"""Chat service for managing chat sessions and conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas import (
    ChatConversation,
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
            """
            SELECT id, user_id, session_data, last_activity, expires_at, created_at, updated_at
            FROM chat_session
            WHERE id = :session_id
            """,
            session_id=session_id,
            schema_type=ChatSession,
            error_message=f"Session {session_id} not found",
        )

    async def get_recent_conversations(
        self,
        session_id: UUID,
        limit: int = 10,
    ) -> list[ChatConversation]:
        """Get recent conversations for a session.

        Args:
            session_id: Session UUID
            limit: Maximum number of conversations to return

        Returns:
            List of recent conversations
        """
        return await self.driver.select(
            """
            SELECT id, session_id, role, content, metadata, intent_classification, created_at
            FROM chat_conversation
            WHERE session_id = :session_id
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            session_id=session_id,
            limit=limit,
            schema_type=ChatConversation,
        )


