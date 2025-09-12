-- Cache management SQL queries for response and embedding caching
-- Complex queries only - simple CRUD operations moved to SQL builder

-- name: get-response-cache-stats
-- Get response cache statistics
SELECT 
    COUNT(*) as total_entries,
    COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL THEN 1 END) as active_entries,
    COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as avg_age_seconds
FROM response_cache;


-- name: get-embedding-cache-stats
-- Get embedding cache statistics
SELECT 
    COUNT(*) as total_embeddings,
    COUNT(DISTINCT model) as unique_models,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as avg_age_seconds,
    model,
    COUNT(*) as count_per_model
FROM embedding_cache
GROUP BY model
ORDER BY count_per_model DESC;

-- name: get-cache-statistics-detailed
-- Get detailed embedding cache statistics with hit metrics
SELECT 
    COUNT(*) as total_embeddings,
    SUM(hit_count) as total_hits,
    AVG(hit_count::float) as avg_hits_per_embedding,
    MAX(last_accessed) as most_recent_access,
    COUNT(CASE WHEN last_accessed > CURRENT_TIMESTAMP - INTERVAL '1 hour' THEN 1 END) as active_last_hour
FROM embedding_cache;

-- Combined Cache Operations

-- name: get-cache-summary
-- Get summary statistics for both cache types
SELECT 
    'response_cache' as cache_type,
    COUNT(*) as total_entries,
    COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL THEN 1 END) as active_entries,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as avg_age_seconds
FROM response_cache
UNION ALL
SELECT 
    'embedding_cache' as cache_type,
    COUNT(*) as total_entries,
    COUNT(*) as active_entries,  -- No expiration for embeddings
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as avg_age_seconds
FROM embedding_cache;

-- name: cleanup-all-caches
-- Cleanup expired entries from both caches
WITH response_cleanup AS (
    DELETE FROM response_cache 
    WHERE expires_at IS NOT NULL 
      AND expires_at < CURRENT_TIMESTAMP
    RETURNING 1
),
embedding_cleanup AS (
    DELETE FROM embedding_cache 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL ':embedding_retention_days days'
    RETURNING 1
)
SELECT 
    (SELECT COUNT(*) FROM response_cleanup) as response_cleanup_count,
    (SELECT COUNT(*) FROM embedding_cleanup) as embedding_cleanup_count;