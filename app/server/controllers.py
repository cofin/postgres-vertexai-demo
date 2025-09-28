"""HTTP controllers for the coffee chat application."""

from __future__ import annotations

import re
import time
import uuid
from typing import TYPE_CHECKING, Annotated, cast

from litestar import Controller, get, post
from litestar.di import Provide
from litestar.plugins.htmx import (
    HTMXRequest,
    HTMXTemplate,
    HXStopPolling,
)
from litestar.response import File, Stream
from litestar_mcp import mcp_tool
from sqlspec.utils.serializers import to_json

from app.server import deps

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from litestar.enums import RequestEncodingType
    from litestar.params import Body

    from app import schemas as s
    from app.services.adk.orchestrator import ADKOrchestrator
    from app.services.metrics import MetricsService
    from app.services.product import ProductService
    from app.services.vertex_ai import VertexAIService


class CoffeeChatController(Controller):
    """Coffee Chat Controller for PostgreSQL demo."""

    dependencies = {
        "adk_orchestrator": Provide(deps.provide_adk_orchestrator),
        "vertex_ai_service": Provide(deps.provide_vertex_ai_service),
        "product_service": Provide(deps.provide_product_service),
        "chat_service": Provide(deps.provide_chat_service),
        "metrics_service": Provide(deps.provide_metrics_service),
    }


    @staticmethod
    def validate_message(message: str) -> str:
        """Validate and sanitize user message input."""
        # Remove any HTML tags
        message = re.sub(r"<[^>]+>", "", message)

        # Limit message length
        max_length = 500
        if len(message) > max_length:
            message = message[:max_length]
        message = message.replace("\x00", "").strip()

        if not message:
            msg = "Message cannot be empty"
            raise ValueError(msg)

        return message


    @get(path="/", name="coffee_chat.show")
    async def show_coffee_chat(self) -> HTMXTemplate:
        """Serve site root."""
        return HTMXTemplate(
            template_name="coffee_chat.html",
            context={},
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": "camera=(), microphone=()",
            },
        )

    @post(path="/", name="coffee_chat.get")
    async def handle_coffee_chat(
        self,
        data: Annotated[s.ChatMessageRequest, Body(title="Coffee Chat", media_type=RequestEncodingType.URL_ENCODED)],
        adk_orchestrator: ADKOrchestrator,
        request: HTMXRequest,
    ) -> HTMXTemplate:
        """Handle both full page and HTMX partial requests using the ADK agent system."""

        clean_message = self.validate_message(data.message)
        validated_persona = data.persona if data.persona in {"novice", "enthusiast", "expert", "barista"} else "enthusiast"
        query_id = str(uuid.uuid4())  # Keep for message fingerprinting

        # Get or create session_id for persistence across requests
        session_id = request.session.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session["session_id"] = session_id

        try:
            # Process through ADK orchestrator with persistent session_id
            agent_response = await adk_orchestrator.process_request(
                query=clean_message,
                user_id="web_user",
                session_id=session_id,  # Use persistent session_id, not query_id
                persona=validated_persona,
            )

        except Exception as e:  # noqa: BLE001
            agent_response = {
                "answer": f"I apologize, but I'm having trouble processing your request right now. Error: {e!s}",
                "products_found": 0,
                "intent": {"intent": "error"},
                "agent_used": "error_fallback",
            }

        if request.htmx:
            return HTMXTemplate(
                template_name="partials/chat_response.html",
                context={
                    "user_message": clean_message,
                    "ai_response": agent_response.get("answer", ""),
                    "query_id": query_id,
                    "products": agent_response.get("products", []),
                    "debug_info": agent_response.get("debug_info", {}),
                    "intent_detected": agent_response.get("debug_info", {}).get("intent", {}).get("intent", "GENERAL"),
                    "from_cache": agent_response.get("from_cache", False),
                    "embedding_cache_hit": agent_response.get("debug_info", {}).get("embedding_cache_hit", False),
                },
                trigger_event="chat:response-complete",
                params={"query_id": query_id, "agent": agent_response.get("agent_used", "ADK")},
                after="settle",
            )

        return HTMXTemplate(
            template_name="coffee_chat.html",
            context={
                "answer": agent_response.get("answer", ""),
                "products": agent_response.get("products", []),
                "agent_used": agent_response.get("agent_used", "ADK"),
            },
        )

    @get(path="/chat/stream/{query_id:str}", name="chat.stream")
    async def stream_response(self, query_id: str, vertex_ai_service: VertexAIService) -> Stream:
        """Stream AI response using Server-Sent Events."""
        # Validate query_id format
        if not re.match(r"^[a-zA-Z0-9_-]+$", query_id):

            async def error_generate() -> AsyncGenerator[str, None]:
                yield "data: {'error': 'Invalid query ID'}\n\n"

            return Stream(error_generate(), media_type="text/event-stream")

        async def generate() -> AsyncGenerator[str, None]:
            try:
                messages = [{"role": "user", "content": "Tell me about coffee recommendations briefly"}]

                # Use real streaming from Vertex AI service
                stream = vertex_ai_service.generate_chat_response_stream(messages)
                async for chunk in stream:
                    if chunk:  # Only send non-empty chunks
                        safe_chunk = chunk.replace('"', '\\"').replace("\n", "\\n")
                        yield f"data: {{'chunk': '{safe_chunk}', 'query_id': '{query_id}'}}\n\n"

                yield f"data: {{'done': true, 'query_id': '{query_id}'}}\n\n"

            except Exception:  # noqa: BLE001
                yield f"data: {{'error': 'Service temporarily unavailable', 'query_id': '{query_id}'}}\n\n"

        return Stream(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @get(path="/dashboard", name="performance_dashboard")
    async def performance_dashboard(self, metrics_service: MetricsService) -> HTMXTemplate:
        """Display performance dashboard."""
        # Get metrics for dashboard
        metrics = await metrics_service.get_performance_metrics(hours_back=24)

        return HTMXTemplate(
            template_name="performance_dashboard.html",
            context={
                "metrics": metrics,
            },
            trigger_event="dashboard:loaded",
            params={"total_searches": metrics.get("total_searches", 0)},
            after="settle",
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
        )

    @get(path="/metrics", name="metrics")
    async def get_metrics(self, metrics_service: MetricsService, request: HTMXRequest) -> dict | HXStopPolling:
        """Get performance metrics."""
        if request.headers.get("X-Requested-With") != "XMLHttpRequest" and not request.htmx:
            return {"error": "Invalid request"}

        try:
            metrics = await metrics_service.get_performance_metrics(hours_back=24)
            if request.htmx and metrics.get("total_searches", 0) == 0:
                return HXStopPolling()
            return {
                "total_searches": int(metrics.get("total_searches", 0)),
                "avg_search_time_ms": float(metrics.get("avg_search_time_ms", 0)),
                "avg_similarity_score": float(metrics.get("avg_similarity_score", 0)),
            }
        except (ValueError, TypeError):
            return {"total_searches": 0, "avg_search_time_ms": 0, "avg_similarity_score": 0}

    @post(path="/api/vector-demo", name="vector.demo")
    @mcp_tool(name="Search Coffee Products")
    async def vector_search_demo(
        self,
        data: Annotated[s.VectorDemoRequest, Body(media_type=RequestEncodingType.URL_ENCODED)],
        vertex_ai_service: VertexAIService,
        product_service: ProductService,
        metrics_service: MetricsService,
        request: HTMXRequest,
    ) -> HTMXTemplate:
        """Interactive vector search demonstration."""
        query = self.validate_message(data.query)

        full_request_start = time.time()
        detailed_timings: dict[str, float] = {}

        # Time the embedding generation
        embedding_start = time.time()
        query_embedding = cast("list[float]", await vertex_ai_service.get_text_embedding(query))
        detailed_timings["embedding_ms"] = (time.time() - embedding_start) * 1000

        # Time the vector search
        search_start = time.time()
        results = await product_service.vector_similarity_search(
            query_embedding=query_embedding,
            similarity_threshold=0.5,
            limit=5,
        )
        detailed_timings["search_ms"] = (time.time() - search_start) * 1000

        # Record metrics
        total_time = (time.time() - full_request_start) * 1000
        await metrics_service.record_search_metric(
            session_id=None,
            query_text=query,
            intent="vector_demo",
            vector_search_results=len(results),
            total_response_time_ms=int(total_time),
            vector_search_time_ms=int(detailed_timings["search_ms"]),
        )

        return HTMXTemplate(
            template_name="partials/vector_results.html",
            context={
                "results": [
                    {
                        "name": r.name,
                        "description": r.description,
                        "similarity": f"{r.similarity_score * 100:.1f}%",
                        "price": f"${r.price:.2f}",
                    }
                    for r in results
                ],
                "search_time": f"{total_time:.0f}ms",
                "embedding_time": f"{detailed_timings['embedding_ms']:.1f}ms",
                "search_time_detail": f"{detailed_timings['search_ms']:.1f}ms",
                "query": query,
            },
            trigger_event="vector:search-complete",
            params={"total_ms": total_time, "results_count": len(results)},
            after="settle",
        )

    @get(
        path="/favicon.ico",
        name="favicon",
        exclude_from_auth=True,
        sync_to_thread=False,
        include_in_schema=False,
    )
    def favicon(self) -> File:
        """Serve favicon."""
        return File(
            path="app/server/static/favicon.ico",
            headers={"Cache-Control": "public, max-age=31536000", "X-Content-Type-Options": "nosniff"},
        )
