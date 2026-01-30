-- name: get-all-products
SELECT
    id,
    name,
    price,
    description,
    category,
    sku,
    COALESCE(in_stock, TRUE) AS in_stock,
    metadata,
    embedding,
    created_at,
    updated_at
FROM product
ORDER BY name;

-- name: get-product-by-id
SELECT
    id,
    name,
    price,
    description,
    category,
    sku,
    COALESCE(in_stock, TRUE) AS in_stock,
    metadata,
    embedding,
    created_at,
    updated_at
FROM product
WHERE id = :id;

-- name: get-product-by-name
SELECT
    id,
    name,
    price,
    description,
    category,
    sku,
    COALESCE(in_stock, TRUE) AS in_stock,
    metadata,
    embedding,
    created_at,
    updated_at
FROM product
WHERE name = :name;

-- name: get-products-without-embeddings
SELECT
    id,
    name,
    price,
    description,
    category,
    sku,
    COALESCE(in_stock, TRUE) AS in_stock,
    metadata,
    embedding,
    created_at,
    updated_at
FROM product
WHERE embedding IS NULL
ORDER BY id;

-- name: search-products-by-vector
SELECT
    id,
    name,
    price,
    description,
    category,
    sku,
    COALESCE(in_stock, TRUE) AS in_stock,
    metadata,
    embedding,
    created_at,
    updated_at,
    1 - (embedding <=> :query_embedding) AS similarity_score
FROM product
WHERE embedding IS NOT NULL
AND 1 - (embedding <=> :query_embedding) >= :similarity_threshold
ORDER BY similarity_score DESC
LIMIT :limit;

-- name: update-product-embedding
UPDATE product
SET embedding = :embedding,
    updated_at = NOW()
WHERE id = :id;

-- name: create-product
INSERT INTO product (
    name, price, description, category, sku, in_stock, metadata, embedding
) VALUES (
    :name, :price, :description, :category, :sku, :in_stock, :metadata, :embedding
)
RETURNING id, name, price, description, category, sku, in_stock, metadata, embedding, created_at, updated_at;

-- name: delete-product
DELETE FROM product WHERE id = :id;
