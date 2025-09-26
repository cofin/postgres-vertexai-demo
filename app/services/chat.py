"""Chat service for managing chat sessions and conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec import sql

from app.schemas import (
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


