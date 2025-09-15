-- Products SQL queries for PostgreSQL + pgvector
-- Complex queries only - simple CRUD operations moved to SQL builder
-- name: full-text-search
-- Full-text search across product names and descriptions
SELECT
  id,
  name,
  description,
  price,
  category,
  sku,
  in_stock,
  metadata,
  created_at,
  updated_at,
  ts_rank(to_tsvector('english', name || ' ' || coalesce(description, '')), plainto_tsquery('english', :query)) as rank
FROM
  product
WHERE
  to_tsvector('english', name || ' ' || coalesce(description, '')) @@ plainto_tsquery('english', :query)
  AND in_stock = true
ORDER BY
  rank DESC,
  name
LIMIT
  :limit_count;


-- name: vector-similarity-search
-- Vector similarity search using cosine distance
SELECT
  id,
  name,
  description,
  price,
  category,
  sku,
  in_stock,
  metadata,
  created_at,
  updated_at,
  1 - (embedding <=> :query_embedding) as similarity_score
FROM
  product
WHERE
  embedding IS NOT NULL
  AND in_stock = true
  AND 1 - (embedding <=> :query_embedding) >= :similarity_threshold
ORDER BY
  embedding <=> :query_embedding
LIMIT
  :limit_count;


-- name: hybrid-search-products
-- Hybrid search combining vector similarity and text search
WITH
  vector_results AS (
    SELECT
      id,
      name,
      description,
      price,
      category,
      sku,
      in_stock,
      metadata,
      created_at,
      updated_at,
      1 - (embedding <=> :query_embedding) as similarity_score,
      'vector' as search_type
    FROM
      product
    WHERE
      embedding IS NOT NULL
      AND in_stock = true
      AND 1 - (embedding <=> :query_embedding) >= :similarity_threshold
    ORDER BY
      embedding <=> :query_embedding
    LIMIT
      :vector_limit
  ),
  text_results AS (
    SELECT
      id,
      name,
      description,
      price,
      category,
      sku,
      in_stock,
      metadata,
      created_at,
      updated_at,
      ts_rank(to_tsvector('english', name || ' ' || coalesce(description, '')), plainto_tsquery('english', :query_text)) as similarity_score,
      'text' as search_type
    FROM
      product
    WHERE
      to_tsvector('english', name || ' ' || coalesce(description, '')) @@ plainto_tsquery('english', :query_text)
      AND in_stock = true
    ORDER BY
      ts_rank(to_tsvector('english', name || ' ' || coalesce(description, '')), plainto_tsquery('english', :query_text)) DESC
    LIMIT
      :text_limit
  )
SELECT
  *
FROM
  vector_results
UNION ALL
SELECT
  *
FROM
  text_results
ORDER BY
  similarity_score DESC;


-- name: get-products-for-embedding
-- Get products that need embedding generation
SELECT
  id,
  name,
  description
FROM
  product
WHERE
  embedding IS NULL
ORDER BY
  created_at
LIMIT
  :batch_size;


-- name: insert-product
-- Insert new product
INSERT INTO
  product (name, description, price, category, sku, in_stock, metadata, embedding)
VALUES
  (:name, :description, :price, :category, :sku, :in_stock, :metadata, :embedding)
RETURNING
  id,
  name,
  description,
  price,
  category,
  sku,
  in_stock,
  metadata,
  created_at,
  updated_at;


-- name: update-product
-- Update existing product
UPDATE product
SET
  name = :name,
  description = :description,
  price = :price,
  category = :category,
  sku = :sku,
  in_stock = :in_stock,
  metadata = :metadata,
  embedding = :embedding,
  updated_at = current_timestamp
WHERE
  id = :id
RETURNING
  id,
  name,
  description,
  price,
  category,
  sku,
  in_stock,
  metadata,
  created_at,
  updated_at;


-- name: update-product-embedding
-- Update product embedding only
UPDATE product
SET
  embedding = :embedding,
  updated_at = current_timestamp
WHERE
  id = :id;


-- name: delete-product
-- Delete product (soft delete by setting in_stock to false)
UPDATE product
SET
  in_stock = false,
  updated_at = current_timestamp
WHERE
  id = :id;


-- name: get-product-categories
-- Get all unique product categories
SELECT DISTINCT
  category
FROM
  product
WHERE
  category IS NOT NULL
  AND in_stock = true
ORDER BY
  category;


-- name: get-products-count
-- Get total count of products
SELECT
  count(*) as total_count
FROM
  product
WHERE
  in_stock = true;


-- name: get-products-paginated
-- Get paginated products
SELECT
  id,
  name,
  description,
  price,
  category,
  sku,
  in_stock,
  metadata,
  created_at,
  updated_at
FROM
  product
WHERE
  in_stock = true
ORDER BY
  created_at DESC
LIMIT
  :limit_count
OFFSET
  :offset_count;