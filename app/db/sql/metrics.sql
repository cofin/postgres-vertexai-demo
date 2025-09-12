-- Search and performance metrics SQL queries
-- Complex queries only - simple CRUD operations moved to SQL builder


-- name: get-recent-metrics
-- Get recent search metrics
SELECT
  sm.id,
  sm.session_id,
  sm.query_text,
  sm.intent,
  sm.confidence_score,
  sm.vector_search_results,
  sm.vector_search_time_ms,
  sm.llm_response_time_ms,
  sm.total_response_time_ms,
  sm.created_at,
  cs.user_id
FROM
  search_metrics sm
  LEFT JOIN chat_session cs ON sm.session_id = cs.id
ORDER BY
  sm.created_at DESC
LIMIT
  :limit_count;


-- name: get-performance-stats
-- Get overall performance statistics
SELECT
  count(*) as total_queries,
  avg(vector_search_time_ms) as avg_vector_search_time_ms,
  avg(llm_response_time_ms) as avg_llm_response_time_ms,
  avg(total_response_time_ms) as avg_total_response_time_ms,
  percentile_cont(0.50) WITHIN GROUP (
    ORDER BY
      total_response_time_ms
  ) as median_response_time_ms,
  percentile_cont(0.95) WITHIN GROUP (
    ORDER BY
      total_response_time_ms
  ) as p95_response_time_ms,
  percentile_cont(0.99) WITHIN GROUP (
    ORDER BY
      total_response_time_ms
  ) as p99_response_time_ms,
  min(total_response_time_ms) as min_response_time_ms,
  max(total_response_time_ms) as max_response_time_ms
FROM
  search_metrics
WHERE
  created_at >= current_timestamp - :hours_back * interval '1 hour';


-- name: get-intent-distribution
-- Get distribution of intents
SELECT
  intent,
  count(*) as query_count,
  avg(confidence_score) as avg_confidence,
  avg(total_response_time_ms) as avg_response_time_ms
FROM
  search_metrics
WHERE
  created_at >= current_timestamp - :hours_back * interval '1 hour'
  AND intent IS NOT NULL
GROUP BY
  intent
ORDER BY
  query_count DESC;


-- name: get-low-confidence-queries
-- Get queries with low confidence scores
SELECT
  id,
  session_id,
  query_text,
  intent,
  confidence_score,
  total_response_time_ms,
  created_at
FROM
  search_metrics
WHERE
  confidence_score < :confidence_threshold
  AND created_at >= current_timestamp - :hours_back * interval '1 hour'
ORDER BY
  confidence_score ASC,
  created_at DESC
LIMIT
  :limit_count;


-- name: get-slow-queries
-- Get queries with slow response times
SELECT
  id,
  session_id,
  query_text,
  intent,
  confidence_score,
  vector_search_time_ms,
  llm_response_time_ms,
  total_response_time_ms,
  created_at
FROM
  search_metrics
WHERE
  total_response_time_ms > :response_time_threshold_ms
  AND created_at >= current_timestamp - :hours_back * interval '1 hour'
ORDER BY
  total_response_time_ms DESC
LIMIT
  :limit_count;


-- name: get-vector-search-performance
-- Get vector search specific performance metrics
SELECT
  count(*) as total_vector_searches,
  avg(vector_search_results) as avg_results_returned,
  avg(vector_search_time_ms) as avg_vector_search_time_ms,
  percentile_cont(0.50) WITHIN GROUP (
    ORDER BY
      vector_search_time_ms
  ) as median_vector_time_ms,
  percentile_cont(0.95) WITHIN GROUP (
    ORDER BY
      vector_search_time_ms
  ) as p95_vector_time_ms,
  count(
    CASE
      WHEN vector_search_results = 0 THEN 1
    END
  ) as zero_result_count,
  count(
    CASE
      WHEN vector_search_results > 0 THEN 1
    END
  ) as with_results_count
FROM
  search_metrics
WHERE
  created_at >= current_timestamp - :hours_back * interval '1 hour'
  AND vector_search_time_ms IS NOT NULL;


-- name: get-daily-metrics-summary
-- Get daily aggregated metrics
SELECT
  date (created_at) as date,
  count(*) as total_queries,
  count(DISTINCT session_id) as unique_sessions,
  avg(total_response_time_ms) as avg_response_time_ms,
  avg(confidence_score) as avg_confidence_score,
  count(
    CASE
      WHEN confidence_score < 0.7 THEN 1
    END
  ) as low_confidence_queries
FROM
  search_metrics
WHERE
  created_at >= current_timestamp - :days_back * interval '1 day'
GROUP BY
  date (created_at)
ORDER BY
  date DESC;


-- name: get-hourly-metrics-summary
-- Get hourly aggregated metrics for today
SELECT
  extract(
    HOUR
    FROM
      created_at
  ) as hour,
  count(*) as total_queries,
  count(DISTINCT session_id) as unique_sessions,
  avg(total_response_time_ms) as avg_response_time_ms,
  avg(confidence_score) as avg_confidence_score
FROM
  search_metrics
WHERE
  date (created_at) = current_date
GROUP BY
  extract(
    HOUR
    FROM
      created_at
  )
ORDER BY
  hour;


-- name: get-user-metrics-summary
-- Get metrics summary by user (via sessions)
SELECT
  cs.user_id,
  count(sm.id) as total_queries,
  count(DISTINCT sm.session_id) as total_sessions,
  avg(sm.confidence_score) as avg_confidence_score,
  avg(sm.total_response_time_ms) as avg_response_time_ms,
  max(sm.created_at) as last_query_at
FROM
  search_metrics sm
  JOIN chat_session cs ON sm.session_id = cs.id
WHERE
  sm.created_at >= current_timestamp - :days_back * interval '1 day'
GROUP BY
  cs.user_id
ORDER BY
  total_queries DESC
LIMIT
  :limit_count;


-- name: cleanup-old-metrics
-- Remove old metrics data
DELETE FROM search_metrics
WHERE
  created_at < current_timestamp - :retention_days * interval '1 day';


-- name: get-metrics-count
-- Get total count of metrics entries
SELECT
  count(*) as total_metrics
FROM
  search_metrics;


-- name: get-metrics-by-date-range
-- Get metrics within a date range
SELECT
  id,
  session_id,
  query_text,
  intent,
  confidence_score,
  vector_search_results,
  vector_search_time_ms,
  llm_response_time_ms,
  total_response_time_ms,
  created_at
FROM
  search_metrics
WHERE
  created_at >= :start_date
  AND created_at <= :end_date
ORDER BY
  created_at DESC
LIMIT
  :limit_count;


-- name: get-search-patterns
-- Analyze search patterns and common queries
SELECT
  query_text,
  count(*) as query_frequency,
  avg(confidence_score) as avg_confidence,
  avg(total_response_time_ms) as avg_response_time,
  count(DISTINCT session_id) as unique_sessions,
  max(created_at) as last_seen
FROM
  search_metrics
WHERE
  created_at >= current_timestamp - :days_back * interval '1 day'
  AND query_text IS NOT NULL
GROUP BY
  query_text
HAVING
  count(*) >= :min_frequency
ORDER BY
  query_frequency DESC
LIMIT
  :limit_count;