# Service Layer Design

## Overview

The service layer follows SQLSpec patterns from the reference applications, providing clean data access with type safety and proper separation of concerns. All services inherit from a base SQLSpec service class.

## Base Service Pattern

### SQLSpec Base Service
Following the accelerator pattern:

```python
# app/services/base.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar

from sqlspec.core.filters import (
    AnyCollectionFilter,
    BeforeAfterFilter,
    FilterTypes,
    FilterTypeT,
    InAnyFilter,
    InCollectionFilter,
    LimitOffsetFilter,
    NotAnyCollectionFilter,
    NotInCollectionFilter,
    NotInSearchFilter,
    OffsetPagination,
    OnBeforeAfterFilter,
    OrderByFilter,
    PaginationFilter,
    SearchFilter,
    StatementFilter,
    apply_filter,
)
from sqlspec.driver import AsyncDriverAdapterBase
from sqlspec.typing import ModelDTOT, StatementParameters

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence
    from sqlspec import QueryBuilder, Statement, StatementConfig

__all__ = (
    "AnyCollectionFilter",
    "BeforeAfterFilter", 
    "FilterTypeT",
    "FilterTypes",
    "InAnyFilter",
    "InCollectionFilter",
    "LimitOffsetFilter",
    "NotAnyCollectionFilter",
    "NotInCollectionFilter", 
    "NotInSearchFilter",
    "OffsetPagination",
    "OnBeforeAfterFilter",
    "OrderByFilter",
    "PaginationFilter",
    "SQLSpecService",
    "SearchFilter",
    "StatementFilter",
    "apply_filter",
)

T = TypeVar("T")
AsyncDriverT = TypeVar("AsyncDriverT", bound=AsyncDriverAdapterBase)

class SQLSpecService:
    """Base service class for SQLSpec operations."""

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize the service."""
        self.driver = driver

    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters | StatementFilter,
        schema_type: type[ModelDTOT],
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[ModelDTOT]:
        """Paginate the data."""
        results, total = await self.driver.select_with_total(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        limit_offset = self.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        return OffsetPagination[ModelDTOT](items=results, limit=limit, offset=offset, total=total)

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[ModelDTOT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> ModelDTOT:
        """Get a single record or raise 404 error if not found."""
        result = await self.driver.select_one_or_none(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        if result is None:
            raise ValueError(error_message or "Record not found")
        return result

    async def exists(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check if a record exists."""
        result = await self.driver.select_one_or_none(
            statement,
            *parameters,
            statement_config=statement_config,
            **kwargs,
        )
        return result is not None

    @staticmethod
    def find_filter(filter_type: type[FilterTypeT], parameters: Sequence[Any]) -> FilterTypeT | None:
        """Find a filter of specific type in parameters."""
        for param in parameters:
            if isinstance(param, filter_type):
                return param
        return None
```

## Core Services

### Product Service

```python
# app/services/_products.py
from __future__ import annotations

import uuid
from typing import Any

from sqlspec import sql
from sqlspec.utils.type_guards import schema_dump

from app import schemas as s
from app.services.base import SQLSpecService


class ProductService(SQLSpecService):
    """Service for product operations."""

    async def vector_search(
        self,
        embedding: list[float],
        threshold: float = 0.7,
        limit: int = 5
    ) -> list[s.ProductWithSimilarity]:
        """Search products by vector similarity."""
        return await self.driver.select(
            sql.query("vector-search-products"),
            {
                "query_embedding": embedding,
                "threshold": threshold,
                "limit": limit
            },
            schema_type=s.ProductWithSimilarity,
        )

    async def get_by_id(self, product_id: uuid.UUID) -> s.Product | None:
        """Get product by ID."""
        return await self.driver.select_one_or_none(
            sql.query("get-product-by-id"),
            {"product_id": product_id},
            schema_type=s.Product,
        )

    async def get_by_name(self, name: str) -> s.Product | None:
        """Get product by name."""
        return await self.driver.select_one_or_none(
            sql.query("get-product-by-name"),
            {"name": name},
            schema_type=s.Product,
        )

    async def search_by_text(
        self,
        query: str,
        limit: int = 10
    ) -> list[s.ProductWithRank]:
        """Full text search fallback."""
        return await self.driver.select(
            sql.query("search-products-by-text"),
            {"query": query, "limit": limit},
            schema_type=s.ProductWithRank,
        )

    async def list_all(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> list[s.Product]:
        """List all products with pagination."""
        return await self.driver.select(
            sql.query("list-all-products"),
            {"limit": limit, "offset": offset},
            schema_type=s.Product,
        )

    async def bulk_upsert_from_fixtures(self, products: list[dict[str, Any]]) -> list[s.ProductUpsertResult]:
        """Bulk upsert products from fixture data."""
        return await self.driver.select(
            sql.query("bulk-upsert-products"),
            {"products_json": products},
            schema_type=s.ProductUpsertResult,
        )

    async def update_embedding(
        self,
        product_id: uuid.UUID,
        embedding: list[float]
    ) -> bool:
        """Update product embedding."""
        result = await self.driver.execute(
            sql.query("update-product-embedding"),
            {
                "product_id": product_id,
                "embedding": embedding
            }
        )
        return result > 0
```

### Chat Service

```python
# app/services/_chat.py
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlspec import sql

from app import schemas as s
from app.services.base import SQLSpecService


class ChatService(SQLSpecService):
    """Service for chat session and conversation management."""

    async def create_session(
        self,
        user_id: str,
        metadata: dict[str, Any] | None = None,
        expires_in_hours: int = 24
    ) -> s.ChatSession:
        """Create a new chat session."""
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        return await self.driver.select_one(
            sql.query("create-chat-session"),
            {
                "user_id": user_id,
                "metadata": metadata or {},
                "expires_at": expires_at
            },
            schema_type=s.ChatSession,
        )

    async def get_active_session(
        self,
        user_id: str
    ) -> s.ChatSession | None:
        """Get the most recent active session for user."""
        return await self.driver.select_one_or_none(
            sql.query("get-active-session"),
            {"user_id": user_id},
            schema_type=s.ChatSession,
        )

    async def get_or_create_session(
        self,
        user_id: str,
        session_id: uuid.UUID | None = None
    ) -> s.ChatSession:
        """Get existing session or create new one."""
        if session_id:
            session = await self.get_session_by_id(session_id)
            if session and not self._is_expired(session):
                return session

        # Try to get active session
        session = await self.get_active_session(user_id)
        if session and not self._is_expired(session):
            return session

        # Create new session
        return await self.create_session(user_id)

    async def get_session_by_id(
        self,
        session_id: uuid.UUID
    ) -> s.ChatSession | None:
        """Get session by ID."""
        return await self.driver.select_one_or_none(
            sql.query("get-session-by-id"),
            {"session_id": session_id},
            schema_type=s.ChatSession,
        )

    async def save_conversation(
        self,
        session_id: uuid.UUID,
        user_message: str,
        assistant_response: str,
        metadata: dict[str, Any] | None = None
    ) -> tuple[s.ChatConversation, s.ChatConversation]:
        """Save both user and assistant messages."""
        
        # Save user message
        user_msg = await self.driver.select_one(
            sql.query("save-conversation"),
            {
                "session_id": session_id,
                "role": "user",
                "content": user_message,
                "metadata": metadata or {}
            },
            schema_type=s.ChatConversation,
        )

        # Save assistant response
        assistant_msg = await self.driver.select_one(
            sql.query("save-conversation"),
            {
                "session_id": session_id,
                "role": "assistant", 
                "content": assistant_response,
                "metadata": metadata or {}
            },
            schema_type=s.ChatConversation,
        )

        return user_msg, assistant_msg

    async def get_conversation_history(
        self,
        session_id: uuid.UUID,
        limit: int = 10
    ) -> list[s.ChatConversation]:
        """Get conversation history for session."""
        return await self.driver.select(
            sql.query("get-conversation-history"),
            {
                "session_id": session_id,
                "limit": limit
            },
            schema_type=s.ChatConversation,
        )

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        return await self.driver.execute(
            sql.query("cleanup-expired-sessions")
        )

    def _is_expired(self, session: s.ChatSession) -> bool:
        """Check if session is expired."""
        if session.expires_at is None:
            return False
        return datetime.utcnow() > session.expires_at
```

### Cache Service

```python
# app/services/_cache.py
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlspec import sql

from app import schemas as s
from app.services.base import SQLSpecService


class CacheService(SQLSpecService):
    """Service for response and embedding caching."""

    # Response Cache Methods
    async def get_cached_response(
        self,
        cache_key: str
    ) -> dict[str, Any] | None:
        """Get cached response if not expired."""
        cached = await self.driver.select_one_or_none(
            sql.query("get-cached-response"),
            {"cache_key": cache_key},
            schema_type=s.ResponseCache,
        )

        if cached and (cached.expires_at is None or cached.expires_at > datetime.utcnow()):
            return cached.response

        return None

    async def cache_response(
        self,
        cache_key: str,
        response: dict[str, Any],
        ttl_minutes: int = 5
    ) -> None:
        """Cache response with expiration."""
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        
        await self.driver.execute(
            sql.query("cache-response"),
            {
                "cache_key": cache_key,
                "response": response,
                "ttl_minutes": ttl_minutes,
                "expires_at": expires_at
            }
        )

    async def invalidate_cache(self, cache_key: str) -> bool:
        """Remove cached response."""
        result = await self.driver.execute(
            sql.query("invalidate-cache"),
            {"cache_key": cache_key}
        )
        return result > 0

    # Embedding Cache Methods
    async def get_cached_embedding(
        self,
        text: str,
        model_name: str = "textembedding-gecko@003"
    ) -> list[float] | None:
        """Get cached embedding for text."""
        text_hash = self._hash_text(text)
        
        cached = await self.driver.select_one_or_none(
            sql.query("get-cached-embedding"),
            {
                "text_hash": text_hash,
                "model_name": model_name
            },
            schema_type=s.EmbeddingCache,
        )

        if cached:
            return cached.embedding

        return None

    async def cache_embedding(
        self,
        text: str,
        embedding: list[float],
        model_name: str = "textembedding-gecko@003"
    ) -> None:
        """Cache embedding for text."""
        text_hash = self._hash_text(text)
        
        await self.driver.execute(
            sql.query("cache-embedding"),
            {
                "text_hash": text_hash,
                "embedding": embedding,
                "model_name": model_name
            }
        )

    # Utility Methods
    async def cleanup_expired_cache(self) -> tuple[int, int]:
        """Clean up expired cache entries."""
        response_count = await self.driver.execute(sql.query("cleanup-expired-responses"))
        
        # Clean up old embeddings (older than 30 days)
        embedding_count = await self.driver.execute(
            sql.query("cleanup-old-embeddings"),
            {"days_old": 30}
        )
        
        return response_count, embedding_count

    def _hash_text(self, text: str) -> str:
        """Generate SHA-256 hash for text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
```

### Metrics Service

```python
# app/services/_metrics.py
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlspec import sql

from app import schemas as s
from app.services.base import SQLSpecService


class MetricsService(SQLSpecService):
    """Service for search and performance metrics."""

    async def record_search(
        self,
        query_id: str,
        user_id: str | None = None,
        search_time_ms: float | None = None,
        embedding_time_ms: float | None = None,
        db_time_ms: float | None = None,
        ai_time_ms: float | None = None,
        similarity_score: float | None = None,
        result_count: int | None = None,
        intent_detected: str = "GENERAL_CONVERSATION",
        cache_hit: bool = False,
        **kwargs: Any
    ) -> s.SearchMetrics:
        """Record search metrics."""
        return await self.driver.select_one(
            sql.query("record-search-metrics"),
            {
                "query_id": query_id,
                "user_id": user_id,
                "search_time_ms": search_time_ms,
                "embedding_time_ms": embedding_time_ms,
                "db_time_ms": db_time_ms,
                "ai_time_ms": ai_time_ms,
                "similarity_score": similarity_score,
                "result_count": result_count,
                "intent_detected": intent_detected,
                "cache_hit": cache_hit
            },
            schema_type=s.SearchMetrics,
        )

    async def record_agent_interaction(
        self,
        query_id: str,
        user_id: str,
        intent: str,
        agent_used: str,
        response_time_ms: float,
        tools_used: list[str] | None = None
    ) -> s.SearchMetrics:
        """Record agent interaction metrics."""
        return await self.record_search(
            query_id=query_id,
            user_id=user_id,
            ai_time_ms=response_time_ms,
            intent_detected=intent,
            cache_hit=False,
            agent_used=agent_used,
            tools_used=tools_used or []
        )

    async def get_performance_stats(
        self,
        hours: int = 24
    ) -> s.PerformanceStats:
        """Get performance statistics for time period."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        return await self.driver.select_one(
            sql.query("get-performance-stats"),
            {"since": since},
            schema_type=s.PerformanceStats,
        )

    async def get_popular_queries(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> list[s.PopularQuery]:
        """Get most popular queries."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        return await self.driver.select(
            sql.query("get-popular-queries"),
            {
                "since": since,
                "limit": limit
            },
            schema_type=s.PopularQuery,
        )

    async def get_cache_hit_rate(
        self,
        hours: int = 24
    ) -> float:
        """Get cache hit rate percentage."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.driver.select_one(
            sql.query("get-cache-hit-rate"),
            {"since": since},
            schema_type=dict,
        )
        
        return result.get("cache_hit_rate", 0.0) if result else 0.0

    async def cleanup_old_metrics(self, days_old: int = 90) -> int:
        """Clean up old metrics data."""
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        
        return await self.driver.execute(
            sql.query("cleanup-old-metrics"),
            {"cutoff": cutoff}
        )
```

## Service Integration

### Agent Service
Orchestrates agent interactions with other services.

```python
# app/services/_agent.py
from __future__ import annotations

import time
import uuid
from typing import Any

from app import schemas as s
from app.services.base import SQLSpecService


class AgentService(SQLSpecService):
    """Service for agent orchestration and management."""

    def __init__(self, 
                 driver,
                 product_service,
                 chat_service,
                 cache_service,
                 metrics_service,
                 vertex_ai_service):
        super().__init__(driver)
        self.product_service = product_service
        self.chat_service = chat_service
        self.cache_service = cache_service
        self.metrics_service = metrics_service
        self.vertex_ai_service = vertex_ai_service
        
        # Initialize agent orchestrator
        from app.agents.coffee_agent import CoffeeAgentOrchestrator
        self.orchestrator = CoffeeAgentOrchestrator(
            product_service=product_service,
            chat_service=chat_service,
            vertex_ai_service=vertex_ai_service,
            metrics_service=metrics_service
        )

    async def process_query(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        use_cache: bool = True
    ) -> s.AgentResponse:
        """Process user query through agent system."""
        
        query_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Check cache first
            if use_cache:
                cache_key = f"agent:{hash(query)}:{user_id}"
                cached_response = await self.cache_service.get_cached_response(cache_key)
                if cached_response:
                    return s.AgentResponse(
                        query_id=query_id,
                        content=cached_response["content"],
                        agent_used=cached_response["agent_used"],
                        tools_used=cached_response["tools_used"],
                        processing_time=time.time() - start_time,
                        from_cache=True
                    )

            # Process through agent orchestrator
            response = await self.orchestrator.process_query(
                query=query,
                user_id=user_id,
                session_id=session_id
            )

            # Cache successful response
            if use_cache:
                await self.cache_service.cache_response(
                    cache_key,
                    {
                        "content": response.content,
                        "agent_used": response.agent_used,
                        "tools_used": response.tools_used
                    },
                    ttl_minutes=5
                )

            return response

        except Exception as e:
            # Log error and return fallback response
            await self.metrics_service.record_search(
                query_id=query_id,
                user_id=user_id,
                search_time_ms=(time.time() - start_time) * 1000,
                result_count=0,
                intent_detected="ERROR"
            )
            
            return s.AgentResponse(
                query_id=query_id,
                content="I apologize, but I'm experiencing technical difficulties. Please try again.",
                agent_used="fallback",
                tools_used=[],
                processing_time=(time.time() - start_time) * 1000,
                error=str(e)
            )

    async def get_agent_stats(self) -> s.AgentStats:
        """Get agent performance statistics."""
        return await self.driver.select_one(
            sql.query("get-agent-stats"),
            schema_type=s.AgentStats,
        )
```

## Service Registration and Dependency Injection

### Service Provider
```python
# app/server/deps.py
from typing import Annotated

from litestar.di import Provide
from sqlspec import AsyncDriverAdapterBase

from app.services import (
    ProductService,
    ChatService,
    CacheService,
    MetricsService,
    AgentService,
)


async def provide_product_service(driver: AsyncDriverAdapterBase) -> ProductService:
    """Provide product service."""
    return ProductService(driver)


async def provide_chat_service(driver: AsyncDriverAdapterBase) -> ChatService:
    """Provide chat service."""
    return ChatService(driver)


async def provide_cache_service(driver: AsyncDriverAdapterBase) -> CacheService:
    """Provide cache service."""
    return CacheService(driver)


async def provide_metrics_service(driver: AsyncDriverAdapterBase) -> MetricsService:
    """Provide metrics service."""
    return MetricsService(driver)


async def provide_agent_service(
    driver: AsyncDriverAdapterBase,
    product_service: Annotated[ProductService, Provide(provide_product_service)],
    chat_service: Annotated[ChatService, Provide(provide_chat_service)],
    cache_service: Annotated[CacheService, Provide(provide_cache_service)],
    metrics_service: Annotated[MetricsService, Provide(provide_metrics_service)],
) -> AgentService:
    """Provide agent service with all dependencies."""
    from app.lib.vertex_ai import VertexAIService
    vertex_ai_service = VertexAIService()
    
    return AgentService(
        driver=driver,
        product_service=product_service,
        chat_service=chat_service,
        cache_service=cache_service,
        metrics_service=metrics_service,
        vertex_ai_service=vertex_ai_service
    )
```

This service layer provides:
- **Clean separation** of concerns
- **Type-safe** operations with msgspec
- **Consistent patterns** across all services
- **Proper error handling** and logging
- **Caching strategies** for performance
- **Metrics collection** for monitoring
- **Easy testing** with dependency injection