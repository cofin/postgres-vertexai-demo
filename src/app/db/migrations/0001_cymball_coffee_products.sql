-- SQLSpec Migration
-- Version: 0001
-- Description: Cymball Coffee Products (PostgreSQL/AlloyDB Omni)
-- Created: 2026-05-05T00:49:23Z
-- Author: Jetski

-- name: migrate-0001-up
CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;

CREATE TABLE product (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2),
    category VARCHAR(100),
    sku VARCHAR(100) UNIQUE,
    in_stock BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    embedding vector(3072),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE store (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(500) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    phone VARCHAR(50),
    latitude DECIMAL(9, 6),
    longitude DECIMAL(9, 6),
    timezone VARCHAR(64),
    google_place_id VARCHAR(255),
    hours JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE store_product_inventory (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES store (id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES product (id) ON DELETE CASCADE,
    quantity_available INTEGER DEFAULT 0 NOT NULL,
    stock_status VARCHAR(20) NOT NULL,
    pickup_available BOOLEAN DEFAULT TRUE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT store_product_inventory_uk UNIQUE (store_id, product_id),
    CHECK (stock_status IN ('IN_STOCK', 'LOW_STOCK', 'OUT_OF_STOCK')),
    CHECK (quantity_available >= 0)
);

CREATE TABLE response_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    response_data JSONB NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE embedding_cache (
    id SERIAL PRIMARY KEY,
    text_hash VARCHAR(255) NOT NULL,
    embedding vector(3072) NOT NULL,
    model VARCHAR(100) NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (text_hash, model)
);

CREATE TABLE search_metric (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    search_time_ms INTEGER,
    embedding_time_ms INTEGER,
    oracle_time_ms INTEGER, -- Kept for compatibility if referenced in code
    ai_time_ms INTEGER DEFAULT 0,
    intent_time_ms INTEGER DEFAULT 0,
    similarity_score DECIMAL,
    result_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
-- ScaNN indexes will be created manually after loading fixtures

CREATE INDEX product_category_idx ON product (category);
CREATE INDEX product_in_stock_idx ON product (in_stock);
CREATE INDEX product_created_at_idx ON product (created_at);

CREATE INDEX store_city_idx ON store (city);
CREATE INDEX store_state_idx ON store (state);
CREATE INDEX store_zip_idx ON store (zip);
CREATE INDEX store_location_idx ON store (latitude, longitude);

CREATE INDEX store_product_inventory_store_idx ON store_product_inventory (store_id);
CREATE INDEX store_product_inventory_product_idx ON store_product_inventory (product_id);
CREATE INDEX store_product_inventory_status_idx ON store_product_inventory (stock_status);
CREATE INDEX store_product_inventory_product_status_idx ON store_product_inventory (product_id, stock_status);

CREATE INDEX response_cache_expires_at_idx ON response_cache (expires_at);
CREATE INDEX response_cache_created_at_idx ON response_cache (created_at);

CREATE INDEX embedding_cache_model_idx ON embedding_cache (model);
CREATE INDEX embedding_cache_created_at_idx ON embedding_cache (created_at);
CREATE INDEX embedding_cache_hit_count_idx ON embedding_cache (hit_count DESC);
CREATE INDEX embedding_cache_last_accessed_idx ON embedding_cache (last_accessed DESC);

CREATE INDEX search_metric_query_id_idx ON search_metric (query_id);
CREATE INDEX search_metric_user_id_idx ON search_metric (user_id);
CREATE INDEX search_metric_created_at_idx ON search_metric (created_at);
CREATE INDEX search_metric_similarity_idx ON search_metric (similarity_score);

-- Full-text search indexes
CREATE INDEX product_name_tsv_idx ON product USING gin (to_tsvector('english', name));
CREATE INDEX product_description_tsv_idx ON product USING gin (to_tsvector('english', description));

-- name: migrate-0001-down
DROP TABLE IF EXISTS search_metric CASCADE;
DROP TABLE IF EXISTS embedding_cache CASCADE;
DROP TABLE IF EXISTS response_cache CASCADE;
DROP TABLE IF EXISTS store_product_inventory CASCADE;
DROP TABLE IF EXISTS store CASCADE;
DROP TABLE IF EXISTS product CASCADE;
DROP EXTENSION IF EXISTS vector CASCADE;
