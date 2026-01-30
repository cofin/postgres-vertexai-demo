-- name: search-similar-intents
SELECT
    intent,
    phrase,
    1 - (embedding <=> :query_embedding) AS similarity,
    confidence_threshold
FROM intent_exemplar
WHERE 1 - (embedding <=> :query_embedding) > :min_threshold
ORDER BY similarity DESC
LIMIT :limit;

-- name: increment-usage-by-phrase
UPDATE intent_exemplar
SET usage_count = usage_count + 1
WHERE intent = :intent AND phrase = :phrase;

-- name: get-exemplars-with-phrases
SELECT
    intent,
    phrase,
    embedding
FROM intent_exemplar
WHERE embedding IS NOT NULL
ORDER BY intent, phrase;

-- name: load-all-exemplars
SELECT
    intent,
    embedding
FROM intent_exemplar
WHERE embedding IS NOT NULL
ORDER BY intent;

-- name: cache-exemplar
INSERT INTO intent_exemplar (intent, phrase, embedding)
VALUES (:intent, :phrase, :embedding)
ON CONFLICT (intent, phrase) DO UPDATE SET
    embedding = EXCLUDED.embedding;

-- name: get-exemplar-embedding
SELECT embedding FROM intent_exemplar
WHERE intent = :intent AND phrase = :phrase;
