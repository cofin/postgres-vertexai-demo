"""WebSocket routes for real-time dashboard and chat.

Provides WebSocket endpoints for:
- Real-time metrics streaming
- Chat with multimodal support
- Connection management
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog
from litestar import Controller, WebSocket, websocket

from cymbal.server.websocket.manager import connection_manager

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class DashboardWebSocketController(Controller):
    """WebSocket endpoints for dashboard real-time updates."""

    path = "/ws/dashboard"

    @websocket("/metrics")
    async def metrics_stream(self, socket: WebSocket) -> None:
        """Stream real-time metrics via WebSocket.

        Replaces HTMX polling with push-based updates.
        """
        async with connection_manager.connect(socket) as conn:
            connection_manager.subscribe(conn.connection_id, "metrics")

            logger.info("Metrics WebSocket connected", connection_id=conn.connection_id)

            try:
                while True:
                    # Wait for client ping or disconnect
                    data = await socket.receive_text()
                    message = json.loads(data)

                    if message.get("action") == "subscribe":
                        # Client requesting specific metrics
                        pass
                    elif message.get("action") == "ping":
                        await socket.send_text(json.dumps({"type": "pong"}))

            except Exception as e:
                logger.debug("Metrics WebSocket error", error=str(e))


class ChatWebSocketController(Controller):
    """WebSocket endpoints for chat with multimodal support."""

    path = "/ws/chat"

    @websocket("/stream")
    async def chat_stream(self, socket: WebSocket) -> None:
        """WebSocket chat with streaming support.

        Supports: text, voice, image
        Replaces SSE streaming from old chat implementation.
        """
        async with connection_manager.connect(socket) as conn:
            connection_manager.subscribe(conn.connection_id, "chat")

            logger.info("Chat WebSocket connected", connection_id=conn.connection_id)

            try:
                while True:
                    # Receive message from client
                    data = await socket.receive_text()
                    message = json.loads(data)

                    msg_type = message.get("type", "text")

                    if msg_type == "text":
                        # Process text message
                        await self._handle_text_message(socket, message)
                    elif msg_type == "voice":
                        # Process voice message (stub for now)
                        await socket.send_text(
                            json.dumps({"type": "ack", "message": "Voice processing not yet implemented"})
                        )
                    elif msg_type == "image":
                        # Process image message (stub for now)
                        await socket.send_text(
                            json.dumps({"type": "ack", "message": "Image processing not yet implemented"})
                        )

            except Exception as e:
                logger.debug("Chat WebSocket error", error=str(e))

    async def _handle_text_message(self, socket: WebSocket, message: dict) -> None:
        """Process a text chat message."""
        content = message.get("content", "")

        # Echo back for now (will integrate with ADK in full implementation)
        response = {"type": "response", "content": f"Received: {content}", "streaming": False}

        await socket.send_text(json.dumps(response))
