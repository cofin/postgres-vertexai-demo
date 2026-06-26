-- SPDX-FileCopyrightText: 2026 Google LLC
-- SPDX-License-Identifier: Apache-2.0

-- name: get-product
SELECT id,
       name,
       description,
       price,
       category,
       sku,
       in_stock,
       metadata,
       embedding,
       created_at,
       updated_at
FROM product;

-- name: list-products
SELECT id,
       name,
       description,
       price,
       category,
       sku,
       in_stock,
       metadata,
       created_at,
       updated_at
FROM product;

-- name: list-products-for-embedding
SELECT id, name, description
FROM product
ORDER BY id;

-- docs:start-vector-search-sql
-- name: vector-search-products
SELECT id,
       name,
       description,
       price,
       1 - (embedding <=> :query_vector) AS similarity_score
FROM product
WHERE 1 - (embedding <=> :query_vector) > :threshold
ORDER BY similarity_score DESC
LIMIT :limit;
-- docs:end-vector-search-sql

-- name: explain-plan-vector-search
EXPLAIN
SELECT id,
       name,
       description,
       price,
       1 - (embedding <=> :query_vector) AS similarity_score
FROM product
WHERE 1 - (embedding <=> :query_vector) > :threshold
ORDER BY similarity_score DESC
LIMIT :limit;
