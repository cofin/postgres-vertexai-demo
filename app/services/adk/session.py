"""Custom ADK Session Service that bridges with our ChatService.

This module provides a BaseSessionService implementation that integrates
ADK session management with our existing chat_session and chat_conversation
infrastructure, using SQLSpec's connection pool management.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from google.adk.events import Event, EventActions
from google.adk.sessions import BaseSessionService, Session
from google.adk.sessions.base_session_service import ListSessionsResponse
from google.genai.types import Content, Part
from sqlspec import sql

from app.schemas.chat import ChatConversation, ChatSession
from app.services.chat import ChatService

if TYPE_CHECKING:
    from concurrent.futures import Executor

    from sqlspec.adapters.asyncpg import AsyncpgConfig

logger = structlog.get_logger()


class ChatSessionService(BaseSessionService):
    """ADK BaseSessionService implementation using our existing chat infrastructure.

    This service bridges ADK session management with our chat_session and
    chat_conversation tables, ensuring proper connection pool usage via
    SQLSpec's provide_session pattern.
    """

    def __init__(self, db_config: AsyncpgConfig, executor: Executor | None = None) -> None:
        """Initialize the chat session service.

        Args:
            db_config: Database configuration for connection management
            executor: Optional executor for async operations (not used in our implementation)
        """
        super().__init__()
        self.db_config = db_config
        self._executor = executor

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        """Create a new ADK session backed by our chat_session table.

        Args:
            app_name: Application name (stored in session_data)
            user_id: User identifier
            state: Initial session state
            session_id: Optional session ID (generated if not provided)

        Returns:
            ADK Session object
        """
        logger.debug("Creating ADK session", app_name=app_name, user_id=user_id, has_initial_state=bool(state))

        # Generate session ID if not provided
        session_id = str(uuid.uuid4()) if session_id is None else str(UUID(session_id))

        # Prepare session data
        session_data = {
            "app_name": app_name,
            "adk_state": state or {},
            "created_by": "adk_session_service",
        }

        async with self.db_config.provide_session() as db_session:
            # Insert the session with our specified ID and return full record
            created_session = await db_session.select_one(
                sql.insert("chat_session")
                .columns("id", "user_id", "session_data", "last_activity", "created_at", "updated_at")
                .values(
                    id=UUID(session_id),
                    user_id=user_id,
                    session_data=session_data,
                    last_activity=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                .returning("id", "user_id", "session_data", "last_activity", "created_at", "updated_at"),
            )
            adk_session = Session(
                id=str(created_session["id"]),
                app_name=app_name,
                user_id=created_session["user_id"],
                state=state or {},
                events=[],
                last_update_time=created_session["last_activity"].timestamp(),
            )

            logger.debug("ADK session created successfully", session_id=session_id, app_name=app_name)

            return adk_session

    async def upsert_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str | None,
        state: dict[str, Any] | None = None,
    ) -> Session:
        """Create or get an existing ADK session.

        Args:
            app_name: Application name (stored in session_data)
            user_id: User identifier
            session_id: Session identifier (generated if None)
            state: Initial session state (only used if creating new session)

        Returns:
            ADK Session object
        """
        # Create new session if no ID provided
        if session_id is None:
            return await self.create_session(
                app_name=app_name,
                user_id=user_id,
                session_id=None,
                state=state,
            )

        # Try to get existing session, create if not found
        existing_session = await self.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        return existing_session or await self.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=state,
        )

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str | None,
        config: Any = None,
    ) -> Session | None:
        """Get an existing ADK session with its events.

        Args:
            app_name: Application name
            user_id: User identifier
            session_id: Session identifier
            config: Optional configuration (not used in our implementation)

        Returns:
            ADK Session object or None if not found
        """
        logger.debug("Getting ADK session", app_name=app_name, user_id=user_id, session_id=session_id)

        # Return None if no session_id provided
        if session_id is None:
            return None

        # Use SQLSpec's session management
        async with self.db_config.provide_session() as db_session:
            chat_service = ChatService(db_session)

            # Get chat session
            try:
                chat_session = await chat_service.get_session_by_session_id(UUID(session_id))
            except ValueError:
                # Session not found
                return None

            # Verify user_id matches
            if chat_session.user_id != user_id:
                logger.warning(
                    "Session user mismatch",
                    session_id=session_id,
                    expected_user=user_id,
                    actual_user=chat_session.user_id,
                )
                return None

            # Get conversation history as events
            conversations = await db_session.select(
                sql.select("id", "session_id", "role", "content", "metadata", "intent_classification", "created_at")
                .from_("chat_conversation")
                .where_eq("session_id", UUID(session_id))
                .order_by("created_at ASC"),  # Chronological order for events
                schema_type=ChatConversation,
            )

            # Convert conversations to ADK events
            events = []
            for conv in conversations:
                # Create ADK event from conversation
                content = Content(parts=[Part(text=conv.content)])

                event = Event(
                    invocation_id=f"conv_{conv.id}",
                    author=conv.role,  # 'user' or 'assistant'
                    content=content,
                    actions=EventActions(
                        state_delta=conv.metadata or {},
                    ),
                    timestamp=(conv.created_at or datetime.now(UTC)).timestamp(),
                )
                events.append(event)

            # Extract ADK state from session data
            session_data = chat_session.session_data or {}
            adk_state = session_data.get("adk_state", {})

            # Create ADK Session
            adk_session = Session(
                id=session_id,
                app_name=app_name,
                user_id=user_id,
                state=adk_state,
                events=events,
                last_update_time=(
                    chat_session.last_activity or chat_session.updated_at or datetime.now(UTC)
                ).timestamp(),
            )

            logger.debug("ADK session retrieved successfully", session_id=session_id, event_count=len(events))

            return adk_session

    async def append_event(self, session: Session, event: Event) -> Event:
        """Append an event to the session and save to chat_conversation.

        Args:
            session: ADK Session object
            event: Event to append

        Returns:
            The appended event
        """
        logger.debug(
            "Appending event to ADK session",
            session_id=session.id,
            author=event.author,
            invocation_id=event.invocation_id,
        )

        # Use SQLSpec's session management
        async with self.db_config.provide_session() as db_session:
            # Extract text content from event
            content_text = ""
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        content_text += part.text

            # Prepare metadata from event actions
            metadata = {}
            if event.actions and event.actions.state_delta:
                metadata.update(event.actions.state_delta)

            # Event metadata is handled through actions.state_delta

            # Insert conversation record with full return data
            conversation_record = await db_session.select_one(
                sql.insert("chat_conversation")
                .columns("session_id", "role", "content", "metadata", "created_at")
                .values(
                    session_id=UUID(session.id),
                    role=event.author,
                    content=content_text,
                    metadata=metadata if metadata else None,
                    created_at=datetime.fromtimestamp(event.timestamp or datetime.now(UTC).timestamp(), UTC),
                )
                .returning("id", "session_id", "role", "content", "metadata", "created_at"),
            )

            # Current timestamp for session updates
            now = datetime.now(UTC)

            # Update session's last activity
            await db_session.execute(
                sql.update("chat_session")
                .set("last_activity", now)
                .set("updated_at", now)
                .where_eq("id", UUID(session.id)),
            )

            # Update session state if event has state delta
            if event.actions and event.actions.state_delta:
                # Update the session object's state
                session.state.update(event.actions.state_delta)

            # Add event to session's event list
            session.events.append(event)
            session.last_update_time = datetime.now(UTC).timestamp()

            logger.debug(
                "Event appended successfully", session_id=session.id, conversation_id=conversation_record["id"],
            )

            return event

    async def list_sessions(self, *, app_name: str, user_id: str) -> ListSessionsResponse:
        """List all sessions for a user in an app.

        Args:
            app_name: Application name
            user_id: User identifier

        Returns:
            List of ADK Session objects (metadata only, no events)
        """
        logger.debug("Listing ADK sessions", app_name=app_name, user_id=user_id)

        # Use SQLSpec's session management
        async with self.db_config.provide_session() as db_session:
            # Query chat sessions for this user and app
            chat_sessions = await db_session.select(
                sql.select("id", "user_id", "session_data", "last_activity", "created_at", "updated_at")
                .from_("chat_session")
                .where_eq("user_id", user_id)
                .where("session_data->>'app_name' = %s", app_name)
                .order_by("created_at DESC"),
                schema_type=ChatSession,
            )

            # Convert to ADK sessions (metadata only)
            sessions = []
            for chat_session in chat_sessions:
                session_data = chat_session.session_data or {}
                adk_state = session_data.get("adk_state", {})

                adk_session = Session(
                    id=str(chat_session.id),
                    app_name=app_name,
                    user_id=user_id,
                    state=adk_state,
                    events=[],  # Don't load events for list operation
                    last_update_time=(
                        chat_session.last_activity or chat_session.updated_at or datetime.now(UTC)
                    ).timestamp(),
                )
                sessions.append(adk_session)

            logger.debug("ADK sessions listed successfully", app_name=app_name, user_id=user_id, count=len(sessions))

            return ListSessionsResponse(sessions=sessions)

    async def delete_session(self, *, app_name: str, user_id: str, session_id: str) -> None:
        """Delete a session and all its conversations.

        Args:
            app_name: Application name
            user_id: User identifier
            session_id: Session identifier
        """
        async with self.db_config.provide_session() as db_session:
            session_uuid = UUID(session_id)

            # Verify session belongs to user and app in single query
            chat_session = await db_session.select_one_or_none(
                sql.select("id", "user_id", "session_data")
                .from_("chat_session")
                .where_eq("id", session_uuid)
                .where_eq("user_id", user_id)
                .where("session_data->>'app_name' = %s", app_name),
                schema_type=ChatSession,
            )

            if not chat_session:
                logger.warning(
                    "Session not found or access denied for deletion",
                    session_id=session_id,
                    user_id=user_id,
                    app_name=app_name,
                )
                return

            # Delete conversations first (foreign key constraint)
            await db_session.execute(sql.delete("chat_conversation").where_eq("session_id", session_uuid))
            await db_session.execute(sql.delete("chat_session").where_eq("id", session_uuid))

            logger.debug("ADK session deleted successfully", session_id=session_id)

    # Optional methods with default implementations

    async def list_events(self, app_name: str, user_id: str, session_id: str) -> list[Event]:
        """List events for a session.

        This is a convenience method that gets the session and returns its events.
        """
        session = await self.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        return session.events if session else []

    async def close_session(self, session: Session) -> None:
        """Close a session (no-op in our implementation).

        Since we use connection pooling, there's no persistent connection to close.
        This method exists to satisfy the BaseSessionService interface.
        """
