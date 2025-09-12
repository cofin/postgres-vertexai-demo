-- Chat session and conversation management SQL queries
-- Complex queries only - simple CRUD operations moved to SQL builder




-- name: get-user-conversation-stats
-- Get conversation statistics for user
SELECT
  count(DISTINCT cs.id) as total_sessions,
  count(cc.id) as total_messages,
  max(cs.last_activity) as last_conversation,
  min(cs.created_at) as first_conversation
FROM
  chat_session cs
  LEFT JOIN chat_conversation cc ON cs.id = cc.session_id
WHERE
  cs.user_id = :user_id
  AND (
    cs.expires_at IS NULL
    OR cs.expires_at > current_timestamp
  );


-- name: search-conversations-by-content
-- Search conversations by content
SELECT
  cc.id,
  cc.session_id,
  cc.role,
  cc.content,
  cc.metadata,
  cc.created_at,
  cs.user_id
FROM
  chat_conversation cc
  JOIN chat_session cs ON cc.session_id = cs.id
WHERE
  to_tsvector('english', cc.content) @@ plainto_tsquery('english', :query)
  AND cs.user_id = :user_id
  AND (
    cs.expires_at IS NULL
    OR cs.expires_at > current_timestamp
  )
ORDER BY
  cc.created_at DESC
LIMIT
  :limit_count;


-- name: get-conversations-by-intent
-- Get conversations filtered by intent metadata
SELECT
  cc.id,
  cc.session_id,
  cc.role,
  cc.content,
  cc.metadata,
  cc.created_at
FROM
  chat_conversation cc
  JOIN chat_session cs ON cc.session_id = cs.id
WHERE
  cc.metadata ->> 'intent' = :intent
  AND cs.user_id = :user_id
  AND (
    cs.expires_at IS NULL
    OR cs.expires_at > current_timestamp
  )
ORDER BY
  cc.created_at DESC
LIMIT
  :limit_count;


-- name: get-active-sessions-count
-- Get count of currently active sessions
SELECT
  count(*) as active_sessions
FROM
  chat_session
WHERE
  (
    expires_at IS NULL
    OR expires_at > current_timestamp
  )
  AND last_activity > current_timestamp - interval ':activity_window_hours hours';


-- name: get-session-summary
-- Get session summary with message counts
SELECT
  cs.id,
  cs.user_id,
  cs.session_data,
  cs.last_activity,
  cs.expires_at,
  cs.created_at,
  count(cc.id) as message_count,
  max(cc.created_at) as last_message_at
FROM
  chat_session cs
  LEFT JOIN chat_conversation cc ON cs.id = cc.session_id
WHERE
  cs.id = :session_id
  AND (
    cs.expires_at IS NULL
    OR cs.expires_at > current_timestamp
  )
GROUP BY
  cs.id,
  cs.user_id,
  cs.session_data,
  cs.last_activity,
  cs.expires_at,
  cs.created_at;