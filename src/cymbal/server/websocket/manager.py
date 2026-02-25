"""WebSocket connection management for real-time features.

Provides connection tracking, authentication, and broadcasting
following the DMA accelerator pattern.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import structlog
from litestar import WebSocket

logger = structlog.get_logger()


@dataclass
class ConnectionInfo:
    """Metadata about a WebSocket connection."""

    connection_id: str
    session_id: str | None
    user_id: str | None
    channels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """Manages WebSocket connections and broadcasting.

    Provides:
    - Connection tracking with metadata
    - Channel-based broadcasting
    - Authentication integration
    - Connection lifecycle management

    Example:
        manager = ConnectionManager()

        @websocket("/ws")
        async def handler(socket: WebSocket) -> None:
            async with manager.connect(socket, session_id="abc") as conn:
                await manager.broadcast("Hello", channel="chat")
    """

    def __init__(self) -> None:
        """Initialize connection manager."""
        self._connections: dict[str, WebSocket] = {}
        self._connection_info: dict[str, ConnectionInfo] = {}
        self._channel_subscribers: dict[str, set[str]] = {}

    @asynccontextmanager
    async def connect(
        self, socket: WebSocket, session_id: str | None = None, user_id: str | None = None
    ) -> AsyncIterator[ConnectionInfo]:
        """Accept and track a new WebSocket connection.

        Args:
            socket: The WebSocket connection
            session_id: Optional session identifier
            user_id: Optional user identifier

        Yields:
            ConnectionInfo for the established connection
        """
        await socket.accept()

        connection_id = str(uuid4())
        info = ConnectionInfo(connection_id=connection_id, session_id=session_id, user_id=user_id)

        self._connections[connection_id] = socket
        self._connection_info[connection_id] = info

        logger.info("WebSocket connected", connection_id=connection_id, session_id=session_id, user_id=user_id)

        try:
            yield info
        finally:
            await self.disconnect(connection_id)

    async def disconnect(self, connection_id: str) -> None:
        """Remove and cleanup a connection.

        Args:
            connection_id: The connection to disconnect
        """
        if connection_id not in self._connections:
            return

        # Remove from all channels
        for channel, subscribers in self._channel_subscribers.items():
            subscribers.discard(connection_id)

        # Cleanup
        del self._connections[connection_id]
        info = self._connection_info.pop(connection_id, None)

        logger.info("WebSocket disconnected", connection_id=connection_id, session_id=info.session_id if info else None)

    def subscribe(self, connection_id: str, channel: str) -> None:
        """Subscribe a connection to a channel.

        Args:
            connection_id: Connection to subscribe
            channel: Channel name to subscribe to
        """
        if channel not in self._channel_subscribers:
            self._channel_subscribers[channel] = set()

        self._channel_subscribers[channel].add(connection_id)

        info = self._connection_info.get(connection_id)
        if info and channel not in info.channels:
            info.channels.append(channel)

        logger.debug("Subscribed to channel", connection_id=connection_id, channel=channel)

    def unsubscribe(self, connection_id: str, channel: str) -> None:
        """Unsubscribe a connection from a channel.

        Args:
            connection_id: Connection to unsubscribe
            channel: Channel name to unsubscribe from
        """
        if channel in self._channel_subscribers:
            self._channel_subscribers[channel].discard(connection_id)

        info = self._connection_info.get(connection_id)
        if info and channel in info.channels:
            info.channels.remove(channel)

        logger.debug("Unsubscribed from channel", connection_id=connection_id, channel=channel)

    async def broadcast(
        self, message: str | dict[str, Any], channel: str | None = None, exclude: str | None = None
    ) -> None:
        """Broadcast a message to all connections or a channel.

        Args:
            message: Message to broadcast (string or JSON object)
            channel: Optional channel to broadcast to (None = all connections)
            exclude: Optional connection_id to exclude from broadcast
        """
        import json

        # Convert dict to JSON string
        if isinstance(message, dict):
            message = json.dumps(message)

        # Get target connections
        if channel:
            target_ids = self._channel_subscribers.get(channel, set()).copy()
        else:
            target_ids = set(self._connections.keys())

        # Exclude sender if specified
        if exclude:
            target_ids.discard(exclude)

        # Send to all targets
        disconnected = []
        for connection_id in target_ids:
            socket = self._connections.get(connection_id)
            if socket:
                try:
                    await socket.send_text(message)
                except Exception:
                    disconnected.append(connection_id)

        # Cleanup disconnected
        for conn_id in disconnected:
            await self.disconnect(conn_id)

    async def send_to(self, connection_id: str, message: str | dict[str, Any]) -> bool:
        """Send a message to a specific connection.

        Args:
            connection_id: Target connection
            message: Message to send

        Returns:
            True if sent successfully, False if connection not found
        """
        import json

        socket = self._connections.get(connection_id)
        if not socket:
            return False

        if isinstance(message, dict):
            message = json.dumps(message)

        try:
            await socket.send_text(message)
            return True
        except Exception:
            await self.disconnect(connection_id)
            return False

    def get_connection_count(self, channel: str | None = None) -> int:
        """Get the number of active connections.

        Args:
            channel: Optional channel to count (None = all)

        Returns:
            Number of connections
        """
        if channel:
            return len(self._channel_subscribers.get(channel, set()))
        return len(self._connections)


# Global connection manager instance
connection_manager = ConnectionManager()
