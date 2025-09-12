# ADK Agent Implementation Plan - ADK Architecture Migration

## CURRENT TASK: Migrate to Google ADK Agents

This migration document outlines the complete replacement of legacy agent code with Google Agent Development Kit (ADK) implementation.

### Previous Work Completed ✅
- Database schema with intent exemplars and vector search
- Service layer with SQLSpec patterns
- CLI management tools
- Two-tier caching system

### Current Focus: Replace Legacy Agent with ADK

---

# Complete ADK Agent Implementation Plan (with Legacy Code Removal)

## Current Analysis:
1. **Legacy Code Removed**: ✅ `app/agents/coffee_agent.py` - traditional service-based implementation
2. **ADK is installed** (`google-adk` in pyproject.toml) but not being used
3. **Agent Execution Context**: Agents will run synchronously per-request (not background processes) as they process user queries in real-time

## Files to Delete Completely:
1. **`app/agents/coffee_agent.py`** - ✅ COMPLETED - Remove entirely (legacy non-ADK implementation)

## New Files to Create:

### 1. **`app/agents/adk_core.py`** - Main ADK Agent System
```python
from google.adk import Agent, Tool, LlmAgent
from google.adk.orchestration import Orchestrator

# Define all ADK agents:
- IntentDetectorAgent (LlmAgent)
- ProductRAGAgent (LlmAgent) 
- ConversationAgent (LlmAgent)
- CoffeeAssistantAgent (main orchestrator)
```

### 2. **`app/agents/tools.py`** - ADK Tool Definitions
```python
# Convert service methods to ADK Tools:
- vector_search_tool
- product_lookup_tool
- session_management_tool
- metrics_recording_tool
```

### 3. **`app/agents/prompts.py`** - Agent Instructions
```python
# System prompts for each agent
INTENT_DETECTOR_PROMPT = "..."
PRODUCT_RAG_PROMPT = "..."
CONVERSATION_PROMPT = "..."
MAIN_ASSISTANT_PROMPT = "..."
```

### 4. **`app/agents/orchestrator.py`** - Request Handler
```python
class ADKOrchestrator:
    """Handles incoming requests and routes to ADK agents"""
    
    async def process_request(self, query: str, session_id: str):
        # This runs synchronously per-request
        # No background process needed
        response = await self.coffee_assistant.process(query)
        return response
```

## Integration Points:

### 1. **Update `app/server/core.py`**:
- Add ADK orchestrator to `on_app_init()`:
```python
def on_app_init(self, app_config: AppConfig):
    # ... existing code ...
    
    # Initialize ADK Orchestrator on app startup
    from app.agents.orchestrator import ADKOrchestrator
    app_config.signature_namespace["ADKOrchestrator"] = ADKOrchestrator
```

### 2. **Update Controllers** to use ADK:
- Modify controllers to use `ADKOrchestrator` instead of old `CoffeeRecommendationAgent`
- Inject orchestrator as dependency

## How Agents Will Run:

**Per-Request Execution** (Not Background):
1. User sends query via HTMX/API
2. Controller receives request
3. Controller calls `orchestrator.process_request()`
4. ADK agents process synchronously:
   - Intent detection
   - Sub-agent routing
   - Tool execution
   - Response generation
5. Response returned to user

**No Background Process Needed** because:
- Agents are stateless
- Each request is independent
- Processing time is <2 seconds
- No persistent agent state required

## Update Requirements Documentation:

### 1. **`requirements/03_agent_implementation.md`**:
- Remove all pseudo-code examples
- Add actual ADK implementation details
- Include real import statements and class definitions

### 2. **`requirements/06_implementation_todo.md`**:
- Mark Phase 3.1 and 3.2 as complete
- Update with actual implementation status

### 3. **`requirements/progress.md`**:
- Add "Phase 3: ADK Agent Implementation" as complete
- Document architectural decisions

## Benefits of This Approach:
1. **Clean Codebase**: No legacy code, pure ADK implementation
2. **Simple Execution Model**: Synchronous per-request, no complex background processes
3. **Clear Separation**: ADK agents handle AI logic, services handle data access
4. **Maintainable**: Following Google's ADK patterns exactly
5. **Performant**: No overhead from background processes or queues

## Implementation Order:
1. ✅ Delete `coffee_agent.py`
2. 🔄 Create ADK tool definitions
3. Create agent prompts
4. Implement ADK agents with proper hierarchy
5. Create orchestrator for request handling
6. Update controllers to use orchestrator
7. Update documentation
8. Test end-to-end flow

This creates a lean, modern agent system using Google ADK without any legacy code.

## Implementation Status:
- [x] Delete legacy coffee_agent.py file
- [ ] Create ADK tool definitions in app/agents/tools.py
- [ ] Create agent prompts in app/agents/prompts.py
- [ ] Implement ADK agents in app/agents/adk_core.py
- [ ] Create orchestrator in app/agents/orchestrator.py
- [ ] Update controllers to use ADK orchestrator
- [ ] Update app/server/core.py to integrate orchestrator
- [ ] Update requirements documentation

---

# Previous Implementation Work - FOR REFERENCE ONLY

This section contains the previous implementation for intent classification and vector search that is already working. The new ADK system will leverage these existing services.

## Current State Analysis

### Architectural Gaps vs Oracle Version

#### 1. Missing Core Features

- **Intent Exemplar System**: Oracle has pre-computed intent embeddings cached in database for fast routing
- **Intent Service**: Oracle uses vector similarity search for intent classification
- **Two-tier Caching**: Oracle has memory + database caching, we only have database
- **Advanced Services**: Missing recommendation, persona_manager, intent routing services

#### 2. Service Architecture Issues

##### Services NOT Inheriting from SQLSpecService

- **EmbeddingService** - SHOULD inherit (manages database cache)
- **VertexAIService** - CORRECT as-is (external API only, no DB operations)

##### Current Service Structure

```
SQLSpecService (base)
├── CacheService ✓
├── ChatService ✓
├── MetricsService ✓
└── ProductService ✓

Standalone (no base):
├── EmbeddingService ✗ (should inherit)
└── VertexAIService ✓ (correct)
```

#### 3. Agent Implementation Deficiencies

- **CoffeeRecommendationAgent** uses primitive keyword matching
- No vector-based intent routing
- No confidence scoring
- No exemplar-based learning

## What Gets REMOVED/REPLACED

### 1. Files to DELETE

```
None - this is additive work
```

### 2. Code to REPLACE

#### app/services/embedding.py

**CURRENT (lines 18-29):**

```python
class EmbeddingService:
    """Service for managing embeddings with caching."""
    
    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize embedding service.
        
        Args:
            driver: Database driver for cache operations
        """
        self.vertex_ai = VertexAIService()
        self.cache_service = CacheService(driver)
```

**REPLACE WITH:**

```python
class EmbeddingService(SQLSpecService):
    """Service for managing embeddings with caching.
    
    Inherits from SQLSpecService to use SQLSpec patterns for database operations.
    Manages both embedding generation and caching with two-tier architecture.
    """
    
    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize embedding service.
        
        Args:
            driver: Database driver for cache operations
        """
        super().__init__(driver)
        self.vertex_ai = VertexAIService()
        self.cache_service = CacheService(driver)
        self._memory_cache: dict[str, list[float]] = {}  # Add memory tier
```

#### app/agents/coffee_agent.py

**CURRENT (lines 57-90) - ENTIRE process_user_intent method:**

```python
# Simple intent classification based on keywords
# In a full ADK implementation, this would use more sophisticated NLU
message_lower = user_message.lower()
# ... keyword matching logic ...
```

**REPLACE WITH:**

```python
# Use vector-based intent classification with exemplars
intent_result = await self.intent_service.classify_intent(
    user_message, 
    user_embedding=await self.embedding.get_text_embedding(user_message)
)
```

#### app/services/cache.py

**CURRENT (lines 84-100) - get_cached_embedding method:**

```python
async def get_cached_embedding(self, text: str, model_name: str) -> EmbeddingCache | None:
    """Get cached embedding for text.
    
    Args:
        text: Text that was embedded
        model_name: Embedding model name
    
    Returns:
        Cached embedding or None if not found
    """
    text_hash = self._hash_text(text)
    return await self.driver.select_one_or_none(
        sqlspec.get_sql("get-cached-embedding"),
        text_hash=text_hash,
        model_name=model_name,
        schema_type=EmbeddingCache,
    )
```

**REPLACE WITH:**

```python
async def get_cached_embedding(self, text: str, model_name: str) -> tuple[list[float] | None, bool]:
    """Get cached embedding with two-tier caching (memory + database).
    
    Args:
        text: Text that was embedded
        model_name: Embedding model name
    
    Returns:
        Tuple of (embedding vector or None, cache_hit boolean)
    """
    # Check memory cache first
    cache_key = f"{text}:{model_name}"
    if cache_key in self._memory_cache:
        await self._increment_hit_count(text_hash)
        return self._memory_cache[cache_key], True
    
    # Check database cache
    text_hash = self._hash_text(text)
    cached = await self.driver.select_one_or_none(
        sqlspec.get_sql("get-cached-embedding"),
        text_hash=text_hash,
        model_name=model_name,
        schema_type=EmbeddingCache,
    )
    
    if cached:
        self._memory_cache[cache_key] = cached.embedding_data
        await self._increment_hit_count(text_hash)
        return cached.embedding_data, True
    
    return None, False
```

### 3. Database Schema Changes

#### MODIFY app/db/migrations/0001_initial_schema_with_pgvector_support.sql

**UPDATE existing tables (note: already singular names):**

**embedding_cache** - ADD columns after line 66:

```sql
CREATE TABLE embedding_cache (
    id serial PRIMARY KEY,
    text_hash varchar(255) UNIQUE NOT NULL,
    embedding vector (768) NOT NULL,
    model varchar(100) NOT NULL,
    hit_count integer DEFAULT 0,  -- ADD THIS
    last_accessed timestamp with time zone DEFAULT current_timestamp,  -- ADD THIS
    created_at timestamp with time zone DEFAULT current_timestamp
);
```

**chat_conversation** - ADD column after line 44:

```sql
CREATE TABLE chat_conversation (
    id serial PRIMARY KEY,
    session_id uuid REFERENCES chat_session (id) ON DELETE CASCADE,
    role varchar(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content text NOT NULL,
    metadata jsonb,
    intent_classification jsonb,  -- ADD THIS (stores intent, confidence, exemplar_match)
    created_at timestamp with time zone DEFAULT current_timestamp
);
```

**search_metrics** - ADD columns after line 78:

```sql
CREATE TABLE search_metrics (
    id serial PRIMARY KEY,
    session_id uuid REFERENCES chat_session (id),
    query_text text,
    intent varchar(100),
    confidence_score real,
    vector_search_results integer,
    vector_search_time_ms integer,
    llm_response_time_ms integer,
    total_response_time_ms integer,
    embedding_cache_hit boolean DEFAULT false,  -- ADD THIS
    intent_exemplar_used varchar(255),  -- ADD THIS
    created_at timestamp with time zone DEFAULT current_timestamp
);
```

**ADD new table intent_exemplar (after embedding_cache table, around line 67):**

```sql
-- Intent exemplars for vector-based intent classification
CREATE TABLE intent_exemplar (
    id serial PRIMARY KEY,
    intent varchar(100) NOT NULL,
    phrase text NOT NULL,
    embedding vector(768) NOT NULL,
    confidence_threshold real DEFAULT 0.7,
    usage_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT current_timestamp,
    updated_at timestamp with time zone DEFAULT current_timestamp,
    UNIQUE(intent, phrase)
);

-- Vector similarity index for fast search
CREATE INDEX intent_exemplar_embedding_ivfflat_idx ON intent_exemplar 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Standard indexes
CREATE INDEX intent_exemplar_intent_idx ON intent_exemplar(intent);
CREATE INDEX intent_exemplar_usage_idx ON intent_exemplar(usage_count DESC);
```

## What Gets ADDED (New Implementation)

### Phase 1: New Services

#### 1.1 IntentExemplarService (NEW FILE)

```python
# app/services/intent_exemplar.py
from app.services.base import SQLSpecService

class IntentExemplarService(SQLSpecService):
    """Manages intent exemplars for vector-based intent classification.
    
    Uses SQLSpec patterns for all database operations.
    Provides CRUD operations and bulk loading for intent exemplars.
    """
    
    async def load_exemplars(self, exemplars: dict[str, list[str]]) -> int:
        """Load intent exemplars with embeddings."""
        
    async def get_exemplars_by_intent(self, intent: str) -> list[IntentExemplar]:
        """Get all exemplars for a specific intent."""
        
    async def search_similar_intents(self, embedding: list[float], threshold: float = 0.7) -> list[tuple[str, float, str]]:
        """Search for similar intents using vector similarity."""
```

#### 1.2 IntentService (NEW FILE)

```python
# app/services/intent.py
from app.services.base import SQLSpecService

class IntentService(SQLSpecService):
    """PostgreSQL native vector similarity search for intent routing.
    
    Uses pgvector for efficient similarity search.
    Integrates with embedding cache for performance.
    """
    
    def __init__(self, driver, exemplar_service, embedding_service):
        super().__init__(driver)
        self.exemplar_service = exemplar_service
        self.embedding_service = embedding_service
    
    async def classify_intent(self, query: str, user_embedding: list[float] | None = None) -> IntentResult:
        """Classify intent using vector similarity with exemplars."""
```

### Phase 2: New SQL Queries

#### 2.1 Intent Exemplar Queries (NEW FILE)

```sql
-- app/db/sql/intent_exemplar.sql (note: singular filename to match table)

-- name: get-intent-exemplars
SELECT id, intent, phrase, embedding, confidence_threshold, usage_count, created_at
FROM intent_exemplar
ORDER BY intent, usage_count DESC;

-- name: upsert-intent-exemplar
INSERT INTO intent_exemplar (intent, phrase, embedding, confidence_threshold)
VALUES (:intent, :phrase, :embedding, :confidence_threshold)
ON CONFLICT (intent, phrase) 
DO UPDATE SET 
    embedding = EXCLUDED.embedding,
    updated_at = NOW()
RETURNING id;

-- name: search-similar-intents
SELECT 
    intent,
    phrase,
    1 - (embedding <=> :query_embedding::vector) as similarity,
    confidence_threshold
FROM intent_exemplar
WHERE 1 - (embedding <=> :query_embedding::vector) > :min_threshold
ORDER BY similarity DESC
LIMIT :limit;

-- name: increment-exemplar-usage
UPDATE intent_exemplar 
SET usage_count = usage_count + 1
WHERE id = :exemplar_id;
```

#### 2.2 Enhanced Cache Queries (UPDATE EXISTING)

```sql
-- app/db/sql/cache.sql (ADD these queries)

-- name: increment-embedding-hit-count
UPDATE embedding_cache 
SET hit_count = hit_count + 1,
    last_accessed = NOW()
WHERE text_hash = :text_hash;

-- name: get-cache-statistics-detailed
SELECT 
    COUNT(*) as total_embeddings,
    SUM(hit_count) as total_hits,
    AVG(hit_count) as avg_hits_per_embedding,
    MAX(last_accessed) as most_recent_access,
    COUNT(CASE WHEN last_accessed > NOW() - INTERVAL '1 hour' THEN 1 END) as active_last_hour
FROM embedding_cache;
```

### Phase 3: New Schemas

#### 3.1 Intent Schemas (NEW FILE)

```python
# app/schemas/intent.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class IntentExemplar(BaseModel):
    """Schema for intent exemplar records."""
    id: int
    intent: str
    phrase: str
    embedding: list[float]
    confidence_threshold: float
    usage_count: int
    created_at: datetime
    updated_at: datetime

class IntentResult(BaseModel):
    """Result of intent classification."""
    intent: str
    confidence: float
    exemplar_phrase: str
    embedding_cache_hit: bool
    fallback_used: bool = False
```

### Phase 4: Configuration

#### 4.1 Intent Configuration (NEW FILE)

```python
# app/config/intents.py

INTENT_EXEMPLARS = {
    "PRODUCT_SEARCH": [
        "What coffee do you have?",
        "Show me your espresso options",
        "I'm looking for a dark roast",
        "Do you have any lattes?",
        "What drinks are available?",
        "Recommend a coffee",
        "What's your strongest coffee?",
    ],
    "PRICE_INQUIRY": [
        "How much does it cost?",
        "What's the price?",
        "Is it expensive?",
        "What's your cheapest option?",
        "Show me drinks under $5",
    ],
    "BREWING_HELP": [
        "How do I make espresso?",
        "What's the best brewing method?",
        "How much coffee should I use?",
        "What temperature for brewing?",
    ],
    "GENERAL_CONVERSATION": [
        "Hello",
        "Thank you",
        "Goodbye",
        "How are you?",
        "Tell me about coffee",
    ],
}

INTENT_THRESHOLDS = {
    "PRODUCT_SEARCH": 0.75,
    "PRICE_INQUIRY": 0.70,
    "BREWING_HELP": 0.72,
    "GENERAL_CONVERSATION": 0.65,
}

VECTOR_SEARCH_CONFIG = {
    "min_similarity_threshold": 0.6,
    "max_results": 10,
    "use_approximate_search": True,  # IVFFlat for performance
}
```

### Phase 5: CLI Commands

#### 5.1 Update app/cli/commands.py (ADD methods)

```python
@app.command()
async def populate_intents(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", "-f", help="Force repopulation"),
) -> None:
    """Populate intent exemplars with embeddings."""
    async with ctx.obj.get_driver() as driver:
        exemplar_service = IntentExemplarService(driver)
        embedding_service = EmbeddingService(driver)
        
        count = 0
        for intent, phrases in INTENT_EXEMPLARS.items():
            for phrase in phrases:
                embedding = await embedding_service.get_text_embedding(phrase)
                await exemplar_service.create_or_update(
                    intent=intent,
                    phrase=phrase,
                    embedding=embedding,
                    confidence_threshold=INTENT_THRESHOLDS.get(intent, 0.7)
                )
                count += 1
        
        typer.echo(f"✓ Populated {count} intent exemplars")

@app.command()
async def test_intent(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Query to test"),
) -> None:
    """Test intent classification for a query."""
    async with ctx.obj.get_driver() as driver:
        intent_service = IntentService(driver)
        result = await intent_service.classify_intent(query)
        
        typer.echo(f"Query: {query}")
        typer.echo(f"Intent: {result.intent}")
        typer.echo(f"Confidence: {result.confidence:.2%}")
        typer.echo(f"Matched: {result.exemplar_phrase}")
```

## Implementation Order

### Step 1: Database Schema Update

1. Modify `app/db/migrations/0001_initial_schema_with_pgvector_support.sql`
2. Drop and recreate database with new schema

### Step 2: Fix Service Inheritance

1. Update `EmbeddingService` to inherit from `SQLSpecService`
2. Add memory cache tier to `CacheService`
3. Update service docstrings explaining patterns

### Step 3: Create New Services

1. Create `IntentExemplarService`
2. Create `IntentService`
3. Create schema files

### Step 4: SQL Queries

1. Create `intent_exemplar.sql`
2. Update `cache.sql` with hit tracking

### Step 5: Configuration

1. Create `intents.py` config
2. Update main config to import intent settings

### Step 6: CLI Integration

1. Add intent management commands
2. Update clear-cache to handle exemplars

### Step 7: Agent Upgrade

1. Replace keyword matching with vector-based intent
2. Add confidence scoring
3. Integrate with new services

## Testing Requirements

### Unit Tests Needed

- `test_intent_exemplar_service.py`
- `test_intent_service.py`
- `test_embedding_service_refactored.py`
- `test_cache_two_tier.py`

### Integration Tests

- Intent classification accuracy
- Cache hit ratio monitoring
- Vector search performance
- Agent conversation flow

### Performance Benchmarks

- Vector similarity search speed
- Memory cache vs database cache
- Intent classification latency
- Bulk embedding generation

## Success Criteria

1. **Intent Classification**: >90% accuracy on known intents
2. **Cache Hit Ratio**: >70% for repeated queries
3. **Response Time**: <100ms for intent classification
4. **Memory Usage**: <100MB for memory cache tier
5. **Agent Quality**: Natural conversation flow with confidence scoring

## Documentation Updates Required

1. **Service Architecture**: Document SQLSpecService inheritance patterns
2. **Intent System**: Explain vector-based classification
3. **Cache Strategy**: Document two-tier caching
4. **Agent Framework**: Document ADK patterns implementation
5. **Migration Guide**: Step-by-step from keyword to vector-based
