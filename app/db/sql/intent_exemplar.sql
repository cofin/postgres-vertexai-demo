-- Intent exemplar SQL queries 
-- Complex queries only - simple CRUD operations moved to SQL builder
-- name: search-similar-intents
WITH
    query_embedding AS (
        SELECT
            intent,
            phrase,
            1 - (embedding <=> :query_embedding) AS similarity,
            confidence_threshold,
            usage_count
        FROM
            intent_exemplar
    )
SELECT
    intent,
    phrase,
    similarity,
    confidence_threshold,
    usage_count
FROM
    query_embedding
WHERE
    similarity > :min_threshold
ORDER BY
    similarity DESC
LIMIT
    :limit;


-- name: search-similar-intents-by-intent
WITH
    query_embedding AS (
        SELECT
            intent,
            phrase,
            1 - (embedding <=> :query_embedding) AS similarity,
            confidence_threshold,
            usage_count
        FROM
            intent_exemplar
    )
SELECT
    intent,
    phrase,
    similarity,
    confidence_threshold,
    usage_count
FROM
    query_embedding
WHERE
    intent = :target_intent
    AND similarity > :min_threshold
ORDER BY
    similarity DESC
LIMIT
    :limit;


-- name: get-intent-stats
SELECT
    count(*) as total_exemplars,
    count(DISTINCT intent) as intents_count,
    avg(usage_count) as average_usage
FROM
    intent_exemplar;


-- name: get-top-intents
SELECT
    intent,
    count(*) as exemplar_count,
    sum(usage_count) as total_usage,
    avg(confidence_threshold) as avg_threshold
FROM
    intent_exemplar
GROUP BY
    intent
ORDER BY
    total_usage DESC,
    exemplar_count DESC
LIMIT
    :limit;


-- name: clean-unused-exemplars
DELETE FROM intent_exemplar
WHERE
    usage_count = 0
    AND created_at < now() - interval ':days_old';