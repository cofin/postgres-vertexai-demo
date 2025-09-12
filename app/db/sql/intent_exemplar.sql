-- Intent exemplar SQL queries 
-- Complex queries only - simple CRUD operations moved to SQL builder

-- name: search-similar-intents
SELECT 
    intent,
    phrase,
    1 - (embedding <=> :query_embedding) as similarity,
    confidence_threshold,
    usage_count
FROM intent_exemplar
WHERE 1 - (embedding <=> :query_embedding) > :min_threshold
ORDER BY similarity DESC
LIMIT :limit;

-- name: search-similar-intents-by-intent
SELECT 
    intent,
    phrase,
    1 - (embedding <=> :query_embedding) as similarity,
    confidence_threshold,
    usage_count
FROM intent_exemplar
WHERE intent = :target_intent
  AND 1 - (embedding <=> :query_embedding) > :min_threshold
ORDER BY similarity DESC
LIMIT :limit;


-- name: get-intent-stats
SELECT 
    COUNT(*) as total_exemplars,
    COUNT(DISTINCT intent) as intents_count,
    AVG(usage_count) as average_usage
FROM intent_exemplar;

-- name: get-top-intents
SELECT 
    intent,
    COUNT(*) as exemplar_count,
    SUM(usage_count) as total_usage,
    AVG(confidence_threshold) as avg_threshold
FROM intent_exemplar
GROUP BY intent
ORDER BY total_usage DESC, exemplar_count DESC
LIMIT :limit;

-- name: clean-unused-exemplars
DELETE FROM intent_exemplar 
WHERE usage_count = 0 
  AND created_at < NOW() - INTERVAL ':days_old days';