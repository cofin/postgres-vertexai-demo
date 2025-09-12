-- Vector Demo Migration
-- Version: 0001
-- Description: Initial schema with pgvector support
-- Created: 2025-09-06T21:07:17.624967+00:00
-- Author: cody
-- name: migrate-0001-up
-- Enable pgvector extension for vector operations
CREATE EXTENSION if NOT EXISTS vector;


-- Products table with vector embeddings for semantic search
CREATE TABLE product (
    id serial PRIMARY KEY,
    name varchar(255) NOT NULL,
    description text,
    price decimal(10, 2),
    category varchar(100),
    sku varchar(100) UNIQUE,
    in_stock boolean DEFAULT true,
    metadata jsonb,
    embedding vector (768), -- 768 dimensions for Vertex AI textembedding-gecko
    created_at timestamp with time zone DEFAULT current_timestamp,
    updated_at timestamp with time zone DEFAULT current_timestamp
);


-- Chat sessions for user conversations
CREATE TABLE chat_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id varchar(255), -- Session identifier
    session_data jsonb, -- Session metadata
    last_activity timestamp with time zone DEFAULT current_timestamp,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT current_timestamp,
    updated_at timestamp with time zone DEFAULT current_timestamp
);


-- Chat conversations for message history
CREATE TABLE chat_conversation (
    id serial PRIMARY KEY,
    session_id uuid REFERENCES chat_session (id) ON DELETE CASCADE,
    role varchar(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content text NOT NULL,
    metadata jsonb, -- Intent classification, confidence scores, etc.
    intent_classification jsonb, -- Stores intent, confidence, exemplar_match
    created_at timestamp with time zone DEFAULT current_timestamp
);


-- Response cache for LLM responses
CREATE TABLE response_cache (
    id serial PRIMARY KEY,
    cache_key varchar(255) UNIQUE NOT NULL, -- Hash of query + context
    response_data jsonb NOT NULL, -- Cached response
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT current_timestamp
);


-- Embedding cache for vector embeddings
CREATE TABLE embedding_cache (
    id serial PRIMARY KEY,
    text_hash varchar(255) UNIQUE NOT NULL, -- Hash of input text
    embedding vector (768) NOT NULL, -- Cached embedding
    model varchar(100) NOT NULL, -- Model used for embedding
    hit_count integer DEFAULT 0, -- Track cache usage
    last_accessed timestamp with time zone DEFAULT current_timestamp, -- Last access time
    created_at timestamp with time zone DEFAULT current_timestamp
);


-- Intent exemplars for vector-based intent classification
CREATE TABLE intent_exemplar (
    id serial PRIMARY KEY,
    intent varchar(100) NOT NULL,
    phrase text NOT NULL,
    embedding vector (768) NOT NULL, -- 768 dimensions for Vertex AI textembedding-gecko
    confidence_threshold real DEFAULT 0.7,
    usage_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT current_timestamp,
    updated_at timestamp with time zone DEFAULT current_timestamp,
    UNIQUE (intent, phrase)
);


-- Search metrics for performance tracking
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
    embedding_cache_hit boolean DEFAULT false,
    intent_exemplar_used varchar(255),
    created_at timestamp with time zone DEFAULT current_timestamp
);


-- Indexes for performance optimization
-- Vector similarity search indexes (IVFFlat for approximate nearest neighbor)
CREATE INDEX product_embedding_ivfflat_idx ON product USING ivfflat (embedding vector_cosine_ops)
WITH
    (lists = 100);


-- Vector similarity index for intent exemplars
CREATE INDEX intent_exemplar_embedding_ivfflat_idx ON intent_exemplar USING ivfflat (embedding vector_cosine_ops)
WITH
    (lists = 100);


-- Full-text search indexes
CREATE INDEX product_name_gin_idx ON product USING gin (to_tsvector('english', name));


CREATE INDEX product_description_gin_idx ON product USING gin (to_tsvector('english', description));


-- Standard B-tree indexes
CREATE INDEX product_category_idx ON product (category);


CREATE INDEX product_in_stock_idx ON product (in_stock);


CREATE INDEX product_created_at_idx ON product (created_at);


CREATE INDEX chat_session_user_id_idx ON chat_session (user_id);


CREATE INDEX chat_session_expires_at_idx ON chat_session (expires_at);


CREATE INDEX chat_session_last_activity_idx ON chat_session (last_activity);


CREATE INDEX chat_conversation_session_id_idx ON chat_conversation (session_id);


CREATE INDEX chat_conversation_created_at_idx ON chat_conversation (created_at);


CREATE INDEX response_cache_expires_at_idx ON response_cache (expires_at);


CREATE INDEX response_cache_created_at_idx ON response_cache (created_at);


CREATE INDEX embedding_cache_model_idx ON embedding_cache (model);


CREATE INDEX embedding_cache_created_at_idx ON embedding_cache (created_at);


CREATE INDEX embedding_cache_hit_count_idx ON embedding_cache (hit_count DESC);


CREATE INDEX embedding_cache_last_accessed_idx ON embedding_cache (last_accessed DESC);


-- Intent exemplar indexes
CREATE INDEX intent_exemplar_intent_idx ON intent_exemplar (intent);


CREATE INDEX intent_exemplar_usage_count_idx ON intent_exemplar (usage_count DESC);


CREATE INDEX search_metrics_session_id_idx ON search_metrics (session_id);


CREATE INDEX search_metrics_intent_idx ON search_metrics (intent);


CREATE INDEX search_metrics_created_at_idx ON search_metrics (created_at);


-- Functions for automatic updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column () returns trigger AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language plpgsql;


-- Trigger for product updated_at
CREATE TRIGGER update_product_updated_at before
UPDATE ON product FOR each ROW
EXECUTE function update_updated_at_column ();


-- Trigger for intent_exemplar updated_at
CREATE TRIGGER update_intent_exemplar_updated_at before
UPDATE ON intent_exemplar FOR each ROW
EXECUTE function update_updated_at_column ();


-- Trigger for chat_session updated_at
CREATE TRIGGER update_chat_session_updated_at before
UPDATE ON chat_session FOR each ROW
EXECUTE function update_updated_at_column ();


-- name: migrate-0001-down
-- Drop triggers and functions
DROP TRIGGER if EXISTS update_chat_session_updated_at ON chat_session cascade;


DROP TRIGGER if EXISTS update_intent_exemplar_updated_at ON intent_exemplar cascade;


DROP TRIGGER if EXISTS update_product_updated_at ON product cascade;


DROP TRIGGER if EXISTS update_products_updated_at ON product cascade;


-- Drop indexes
DROP INDEX if EXISTS intent_exemplar_usage_count_idx;


DROP INDEX if EXISTS intent_exemplar_intent_idx;


DROP INDEX if EXISTS intent_exemplar_embedding_ivfflat_idx;


DROP INDEX if EXISTS embedding_cache_last_accessed_idx;


DROP INDEX if EXISTS embedding_cache_hit_count_idx;


DROP INDEX if EXISTS product_embedding_ivfflat_idx;


DROP INDEX if EXISTS product_name_gin_idx;


DROP INDEX if EXISTS product_description_gin_idx;


DROP INDEX if EXISTS product_category_idx;


DROP INDEX if EXISTS product_in_stock_idx;


DROP INDEX if EXISTS product_created_at_idx;


DROP INDEX if EXISTS chat_session_user_id_idx;


DROP INDEX if EXISTS chat_session_expires_at_idx;


DROP INDEX if EXISTS chat_session_last_activity_idx;


DROP INDEX if EXISTS chat_conversation_session_id_idx;


DROP INDEX if EXISTS chat_conversation_created_at_idx;


DROP INDEX if EXISTS response_cache_expires_at_idx;


DROP INDEX if EXISTS response_cache_created_at_idx;


DROP INDEX if EXISTS embedding_cache_model_idx;


DROP INDEX if EXISTS embedding_cache_created_at_idx;


DROP INDEX if EXISTS search_metrics_session_id_idx;


DROP INDEX if EXISTS search_metrics_intent_idx;


DROP INDEX if EXISTS search_metrics_created_at_idx;


-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS search_metrics cascade;


DROP TABLE IF EXISTS intent_exemplar cascade;


DROP TABLE IF EXISTS embedding_cache cascade;


DROP TABLE IF EXISTS response_cache cascade;


DROP TABLE IF EXISTS chat_conversation cascade;


DROP TABLE IF EXISTS chat_session cascade;


DROP TABLE IF EXISTS product cascade;


DROP FUNCTION if EXISTS update_updated_at_column () cascade;


-- Drop extension
DROP EXTENSION if EXISTS vector cascade;
