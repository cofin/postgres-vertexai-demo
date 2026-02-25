-- name: get-all-stores
SELECT * FROM store ORDER BY name;

-- name: find-stores-by-city
SELECT * FROM store WHERE city = :city ORDER BY name;

-- name: find-stores-by-state
SELECT * FROM store WHERE state = :state ORDER BY city, name;

-- name: get-store-by-id
SELECT * FROM store WHERE id = :store_id;

-- name: get-store-hours
SELECT hours FROM store WHERE id = :store_id;

-- name: search-stores-by-zip
SELECT * FROM store WHERE zip = :zip_code ORDER BY name;
