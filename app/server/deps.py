"""Dependency providers for PostgreSQL-based services using SQLSpec."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from app.config import db, sqlspec
from app.services.cache import CacheService
from app.services.chat import ChatService
from app.services.embedding import EmbeddingService
from app.services.metrics import MetricsService
from app.services.product import ProductService
from app.services.vertex_ai import VertexAIService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable


# Generic service provider factory
T = TypeVar("T")


def create_service_provider(service_cls: type[T]) -> Callable[..., AsyncGenerator[T, None]]:
    """Create a generic service provider for services that require a database driver."""

    async def provider() -> AsyncGenerator[T, None]:
        """Generic provider function using SQLSpec's built-in database management."""
        # Use SQLSpec's database configuration to provide a session
        async with sqlspec.provide_session(db) as session:
            yield service_cls(session)  # type: ignore[call-arg]

    return provider


provide_product_service = create_service_provider(ProductService)
provide_chat_service = create_service_provider(ChatService)
provide_cache_service = create_service_provider(CacheService)
provide_metrics_service = create_service_provider(MetricsService)
provide_embedding_service = create_service_provider(EmbeddingService)


# Providers that don't require a database connection directly
async def provide_vertex_ai_service() -> AsyncGenerator[VertexAIService, None]:
    """Provide Vertex AI service."""
    yield VertexAIService()


# ADK Orchestrator provider
async def provide_adk_orchestrator() -> AsyncGenerator[Any, None]:
    """Provide ADK orchestrator with all required services."""
    from app.agents.orchestrator import create_orchestrator

    async with sqlspec.provide_session(db) as session:
        orchestrator = create_orchestrator(session)
        yield orchestrator
