# Database Design and Schema

## Overview

The application uses PostgreSQL with the pgvector extension for efficient vector similarity search. SQLSpec manages all database operations, migrations, and query loading.

## Database Schema

### Core Tables

#### products

```sql
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    description TEXT,
    price DECIMAL(10,2),
    embedding vector(768),  -- Vertex AI embeddings
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector similarity search index
CREATE INDEX idx_products_embedding ON products 
USING ivfflat (embedding vector_cosine_ops);

-- Text search index
CREATE INDEX idx_products_name_desc ON products 
USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));
```

#### chat_session

```sql
CREATE TABLE chat_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    session_metadata JSONB DEFAULT '{}',
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_session_user ON chat_session(user_id);
CREATE INDEX idx_chat_session_expires ON chat_session(expires_at);
```

#### chat_conversation

```sql
CREATE TABLE chat_conversation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_conversation_session ON chat_conversation(session_id);
CREATE INDEX idx_chat_conversation_created ON chat_conversation(created_at DESC);
```

### Caching Tables

#### response_cache

```sql
CREATE TABLE response_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    response JSONB NOT NULL,
    ttl_minutes INT DEFAULT 5,
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '5 minutes',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_response_cache_key ON response_cache(cache_key);
CREATE INDEX idx_response_cache_expires ON response_cache(expires_at);

-- Auto-cleanup function
CREATE OR REPLACE FUNCTION cleanup_expired_cache() RETURNS void AS $$
BEGIN
    DELETE FROM response_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;
```

#### embedding_cache

```sql
CREATE TABLE embedding_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 hash
    embedding vector(768) NOT NULL,
    model_name VARCHAR DEFAULT 'textembedding-gecko@003',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embedding_cache_hash ON embedding_cache(text_hash);
```

### Metrics Table

#### search_metrics

```sql
CREATE TABLE search_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id VARCHAR NOT NULL,
    user_id VARCHAR,
    search_time_ms FLOAT,
    embedding_time_ms FLOAT,
    db_time_ms FLOAT,
    ai_time_ms FLOAT,
    similarity_score FLOAT,
    result_count INT,
    intent_detected VARCHAR DEFAULT 'GENERAL_CONVERSATION',
    cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_search_metrics_created ON search_metrics(created_at DESC);
CREATE INDEX idx_search_metrics_user ON search_metrics(user_id);
```

## Migration Strategy

### Migration Files Structure

```
app/db/migrations/
├── 0001_initial_schema.sql
├── 0002_add_indexes.sql
├── 0003_add_cache_cleanup.sql
└── 0004_performance_optimizations.sql
```

### Migration File Format

```sql
-- SQLSpec Migration
-- Version: 0001
-- Description: Initial schema with pgvector
-- Created: 2025-09-06T00:00:00.000000+00:00
-- Author: system

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tables go here...
```

## SQL Query Organization

### Query Files Structure

```
app/db/sql/
├── products.sql      # Product operations
├── chat.sql         # Chat session management
├── cache.sql        # Caching operations
├── metrics.sql      # Analytics queries
└── admin.sql        # Administrative operations
```

### Sample Query File (products.sql)

```sql
-- name: vector-search-products
-- Search products by vector similarity
SELECT 
    id, 
    name, 
    description, 
    price,
    1 - (embedding <=> :query_embedding::vector) as similarity,
    metadata
FROM products
WHERE embedding <=> :query_embedding::vector < :threshold
ORDER BY embedding <=> :query_embedding::vector
LIMIT :limit;

-- name: get-product-by-id
SELECT * FROM products WHERE id = :product_id;

-- name: search-products-by-text
-- Full text search fallback
SELECT 
    id, 
    name, 
    description, 
    price,
    ts_rank(to_tsvector('english', name || ' ' || COALESCE(description, '')), 
            plainto_tsquery('english', :query)) as rank,
    metadata
FROM products
WHERE to_tsvector('english', name || ' ' || COALESCE(description, ''))
      @@ plainto_tsquery('english', :query)
ORDER BY rank DESC
LIMIT :limit;

-- name: bulk-upsert-products
-- Bulk insert/update products from fixtures
INSERT INTO products (id, name, description, price, embedding, metadata)
SELECT 
    COALESCE(p.id, gen_random_uuid()),
    p.name,
    p.description,
    p.price::decimal,
    p.embedding::vector,
    p.metadata::jsonb
FROM jsonb_to_recordset(:products_json) AS p(
    id uuid,
    name varchar,
    description text,
    price text,
    embedding text,
    metadata jsonb
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    embedding = EXCLUDED.embedding,
    metadata = EXCLUDED.metadata,
    updated_at = NOW()
RETURNING id, name;
```

## Fixture Data Structure

### Product Fixture Format (PRODUCT.json.gz)

```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Ethiopian Yirgacheffe",
    "description": "Bright and floral single-origin coffee with citrus notes",
    "price": "24.99",
    "embedding": [0.1, 0.2, 0.3, ...],
    "metadata": {
      "origin": "Ethiopia",
      "roast_level": "Light",
      "processing": "Washed",
      "tasting_notes": ["citrus", "floral", "bright"],
      "certifications": ["organic", "fair-trade"]
    }
  }
]
```

## Performance Considerations

### Vector Search Optimization

- **ivfflat index**: Optimized for high-speed approximate search
- **Embedding dimension**: 768 for Vertex AI text embeddings
- **Distance metric**: Cosine similarity for semantic search
- **Index parameters**: Tuned for 1000+ products

### Query Optimization

- **Prepared statements**: All queries use SQLSpec named queries
- **Connection pooling**: Configured for high concurrency
- **Index coverage**: All frequent queries have supporting indexes
- **Cache strategy**: Multi-level caching (application + database)

### Scaling Considerations

- **Partitioning**: chat_conversation by date if needed
- **Archiving**: Metrics data rotation after 90 days
- **Read replicas**: For analytics queries if traffic grows
- **Vector index tuning**: Adjust based on dataset size

## Data Migration from Oracle

### Migration Steps

1. **Export Oracle data** using existing fixtures
2. **Transform embeddings** from Oracle format to pgvector
3. **Convert CLOB/BLOB** to PostgreSQL TEXT/BYTEA
4. **Adjust primary keys** to UUID format
5. **Update relationships** to use proper foreign keys

### Data Transformation Script

```python
# Convert Oracle fixture to PostgreSQL format
def transform_oracle_to_postgres(oracle_data):
    return {
        "id": str(uuid.uuid4()),
        "name": oracle_data["NAME"],
        "description": oracle_data["DESCRIPTION"],
        "price": str(oracle_data["CURRENT_PRICE"]),
        "embedding": oracle_data["EMBEDDING"],  # Already in correct format
        "metadata": {
            "company_name": oracle_data.get("COMPANY_NAME"),
            "created_at": oracle_data.get("CREATED_AT"),
            # Additional metadata
        }
    }
```

## Backup and Recovery

### Backup Strategy

- **Daily full backups** of entire database
- **Continuous WAL archiving** for point-in-time recovery
- **Fixture exports** as additional data portability
- **Vector index recreation** scripts for disaster recovery

### Recovery Procedures

1. **Standard recovery**: From daily backup
2. **Point-in-time**: Using WAL replay
3. **Fixture restore**: Using gzipped JSON data
4. **Index rebuild**: For performance optimization
