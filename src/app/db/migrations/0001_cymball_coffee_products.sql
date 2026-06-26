-- SPDX-FileCopyrightText: 2026 Google LLC
-- SPDX-License-Identifier: Apache-2.0

-- SQLSpec Migration
-- Version: 0001
-- Description: Cymball Coffee Products (PostgreSQL with pgvector)
-- Created: 2025-10-30T00:00:00+00:00
-- Author: Cody Fincher <cody@litestar.dev>

-- name: migrate-0001-up

-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS alloydb_scann;

-- Products table with vector embeddings for semantic search
CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2),
    category VARCHAR(100),
    sku VARCHAR(100) UNIQUE,
    in_stock BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    embedding vector(3072),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE product IS 'Products with vector embeddings for semantic search';
COMMENT ON COLUMN product.embedding IS '3072-dimensional vector for Vertex AI text-embedding-004';
COMMENT ON COLUMN product.in_stock IS 'Boolean: true=in stock, false=out of stock';
COMMENT ON COLUMN product.metadata IS 'Product metadata stored as JSONB for efficient querying';


-- Store locations for coffee shop finder
CREATE TABLE store (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(500) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    phone VARCHAR(50),
    hours JSONB,
    metadata JSONB,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    timezone VARCHAR(64),
    google_place_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE store IS 'Coffee shop store locations';
COMMENT ON COLUMN store.hours IS 'Business hours by day: {"monday": "7am-9pm", ...}';
COMMENT ON COLUMN store.metadata IS 'Additional store metadata in JSONB format';

-- Store Product Inventory Table
CREATE TABLE store_product_inventory (
    id BIGSERIAL PRIMARY KEY,
    store_id BIGINT REFERENCES store(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES product(id) ON DELETE CASCADE,
    quantity_available INTEGER NOT NULL CHECK (quantity_available >= 0),
    stock_status VARCHAR(20) NOT NULL CHECK (stock_status IN ('IN_STOCK', 'LOW_STOCK', 'OUT_OF_STOCK')),
    pickup_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT store_product_uk UNIQUE (store_id, product_id)
);

COMMENT ON TABLE store_product_inventory IS 'Inventory of products at each store location';


-- Response cache for LLM responses
CREATE TABLE response_cache (
    id BIGSERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    response_data JSONB NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE response_cache IS 'Cached LLM responses to reduce API calls';
COMMENT ON COLUMN response_cache.cache_key IS 'Hash of query + context for cache lookup';
COMMENT ON COLUMN response_cache.response_data IS 'Cached response data as JSONB';


-- Embedding cache for vector embeddings
CREATE TABLE embedding_cache (
    id BIGSERIAL PRIMARY KEY,
    text_hash VARCHAR(255) NOT NULL,
    embedding vector(3072) NOT NULL,
    model VARCHAR(100) NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT embedding_cache_uk UNIQUE (text_hash, model)
);

COMMENT ON TABLE embedding_cache IS 'Cached embeddings to reduce Vertex AI API calls';
COMMENT ON COLUMN embedding_cache.text_hash IS 'MD5 hash of input text';
COMMENT ON COLUMN embedding_cache.embedding IS '3072-dimensional embedding vector';





-- Search metrics for performance tracking
CREATE TABLE search_metric (
    id BIGSERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    search_time_ms NUMERIC,
    embedding_time_ms NUMERIC,
    db_query_time_ms NUMERIC,
    ai_time_ms NUMERIC DEFAULT 0,
    intent_time_ms NUMERIC DEFAULT 0,
    similarity_score NUMERIC,
    result_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE search_metric IS 'Search performance metrics for vector search operations';
COMMENT ON COLUMN search_metric.query_id IS 'Unique identifier for each search query';
COMMENT ON COLUMN search_metric.user_id IS 'User or session performing the search';
COMMENT ON COLUMN search_metric.search_time_ms IS 'Total search time in milliseconds';
COMMENT ON COLUMN search_metric.embedding_time_ms IS 'Vertex AI embedding generation time in milliseconds';
COMMENT ON COLUMN search_metric.db_query_time_ms IS 'PostgreSQL vector search time in milliseconds';
COMMENT ON COLUMN search_metric.similarity_score IS 'Average similarity score of search results';


-- Indexes for performance optimization

-- AlloyDB ScaNN Vector Indexes
SET scann.enable_index_with_insufficient_data = true;

CREATE INDEX product_embedding_idx ON product USING scann (embedding cosine);
CREATE INDEX embedding_cache_embedding_idx ON embedding_cache USING scann (embedding cosine);


-- Standard B-tree indexes for product table
CREATE INDEX product_category_idx ON product (category);
CREATE INDEX product_in_stock_idx ON product (in_stock);
CREATE INDEX product_created_at_idx ON product (created_at);


-- Store indexes for location queries
CREATE INDEX store_city_idx ON store (city);
CREATE INDEX store_state_idx ON store (state);
CREATE INDEX store_zip_idx ON store (zip);
CREATE INDEX store_location_idx ON store (latitude, longitude);
CREATE INDEX store_product_inventory_store_idx ON store_product_inventory (store_id);
CREATE INDEX store_product_inventory_product_idx ON store_product_inventory (product_id);
CREATE INDEX store_product_inventory_status_idx ON store_product_inventory (stock_status);
CREATE INDEX store_product_inventory_product_status_idx ON store_product_inventory (product_id, stock_status);


-- Cache indexes for expiration and lookup
CREATE INDEX response_cache_expires_at_idx ON response_cache (expires_at);
CREATE INDEX response_cache_created_at_idx ON response_cache (created_at);


-- Embedding cache indexes
CREATE INDEX embedding_cache_model_idx ON embedding_cache (model);
CREATE INDEX embedding_cache_created_at_idx ON embedding_cache (created_at);
CREATE INDEX embedding_cache_hit_count_idx ON embedding_cache (hit_count DESC);
CREATE INDEX embedding_cache_last_accessed_idx ON embedding_cache (last_accessed DESC);




-- Search metrics indexes
CREATE INDEX search_metric_query_id_idx ON search_metric (query_id);
CREATE INDEX search_metric_user_id_idx ON search_metric (user_id);
CREATE INDEX search_metric_created_at_idx ON search_metric (created_at);
CREATE INDEX search_metric_similarity_idx ON search_metric (similarity_score);


-- PostgreSQL full-text search indexes using GIN
CREATE INDEX product_name_text_idx ON product USING gin(to_tsvector('english', name));
CREATE INDEX product_description_text_idx ON product USING gin(to_tsvector('english', description));




-- JSONB indexes for efficient querying
CREATE INDEX product_metadata_idx ON product USING gin(metadata);
CREATE INDEX store_metadata_idx ON store USING gin(metadata);
CREATE INDEX store_hours_idx ON store USING gin(hours);


-- Triggers for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_product_updated_at
    BEFORE UPDATE ON product
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_store_updated_at
    BEFORE UPDATE ON store
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_response_cache_updated_at
    BEFORE UPDATE ON response_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();



CREATE TRIGGER update_search_metric_updated_at
    BEFORE UPDATE ON search_metric
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_store_product_inventory_updated_at
    BEFORE UPDATE ON store_product_inventory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- name: migrate-0001-down

-- Drop inventory trigger and table
DROP TRIGGER IF EXISTS update_store_product_inventory_updated_at ON store_product_inventory;
DROP INDEX IF EXISTS store_product_inventory_product_status_idx;
DROP INDEX IF EXISTS store_product_inventory_status_idx;
DROP INDEX IF EXISTS store_product_inventory_product_idx;
DROP INDEX IF EXISTS store_product_inventory_store_idx;
DROP INDEX IF EXISTS store_location_idx;
DROP TABLE IF EXISTS store_product_inventory CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS update_search_metric_updated_at ON search_metric;
DROP TRIGGER IF EXISTS update_response_cache_updated_at ON response_cache;
DROP TRIGGER IF EXISTS update_store_updated_at ON store;
DROP TRIGGER IF EXISTS update_product_updated_at ON product;
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop indexes
DROP INDEX IF EXISTS product_metadata_idx;
DROP INDEX IF EXISTS store_metadata_idx;
DROP INDEX IF EXISTS store_hours_idx;
DROP INDEX IF EXISTS product_description_text_idx;
DROP INDEX IF EXISTS product_name_text_idx;
DROP INDEX IF EXISTS search_metric_similarity_idx;
DROP INDEX IF EXISTS search_metric_created_at_idx;
DROP INDEX IF EXISTS search_metric_user_id_idx;
DROP INDEX IF EXISTS search_metric_query_id_idx;

DROP INDEX IF EXISTS embedding_cache_last_accessed_idx;
DROP INDEX IF EXISTS embedding_cache_hit_count_idx;
DROP INDEX IF EXISTS embedding_cache_created_at_idx;
DROP INDEX IF EXISTS embedding_cache_model_idx;
DROP INDEX IF EXISTS response_cache_created_at_idx;
DROP INDEX IF EXISTS response_cache_expires_at_idx;
DROP INDEX IF EXISTS store_zip_idx;
DROP INDEX IF EXISTS store_state_idx;
DROP INDEX IF EXISTS store_city_idx;
DROP INDEX IF EXISTS product_created_at_idx;
DROP INDEX IF EXISTS product_in_stock_idx;
DROP INDEX IF EXISTS product_category_idx;
DROP INDEX IF EXISTS embedding_cache_embedding_idx;
DROP INDEX IF EXISTS product_embedding_idx;

-- Drop tables
DROP TABLE IF EXISTS search_metric CASCADE;
DROP TABLE IF EXISTS embedding_cache CASCADE;
DROP TABLE IF EXISTS response_cache CASCADE;
DROP TABLE IF EXISTS store CASCADE;
DROP TABLE IF EXISTS product CASCADE;

-- Drop extension
DROP EXTENSION IF EXISTS alloydb_scann;
DROP EXTENSION IF EXISTS vector;
