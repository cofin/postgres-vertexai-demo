# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

import pytest

pytestmark = pytest.mark.anyio


async def test_vector_dimensions():
    from app.config import db, db_manager
    async with db_manager.provide_session(db) as driver:
        # Check product embedding
        res = await driver.select(
            "SELECT format_type(atttypid, atttypmod) as type FROM pg_attribute WHERE attrelid = 'product'::regclass AND attname = 'embedding'"
        )
        assert res[0]["type"] == "vector(3072)"

        # Check embedding_cache embedding
        res = await driver.select(
            "SELECT format_type(atttypid, atttypmod) as type FROM pg_attribute WHERE attrelid = 'embedding_cache'::regclass AND attname = 'embedding'"
        )
        assert res[0]["type"] == "vector(3072)"


async def test_store_columns():
    from app.config import db, db_manager
    async with db_manager.provide_session(db) as driver:
        res = await driver.select(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'store' AND column_name IN ('latitude', 'longitude', 'timezone', 'google_place_id')"
        )
        columns = {row["column_name"]: row["data_type"] for row in res}
        assert "latitude" in columns
        assert "longitude" in columns
        assert "timezone" in columns
        assert "google_place_id" in columns

        assert columns["latitude"] == "numeric"
        assert columns["longitude"] == "numeric"
        assert columns["timezone"] == "character varying"
        assert columns["google_place_id"] == "character varying"


async def test_inventory_table():
    from app.config import db, db_manager
    async with db_manager.provide_session(db) as driver:
        # Check if table exists
        res = await driver.select(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'store_product_inventory'"
        )
        assert len(res) == 1
        assert res[0]["table_name"] == "store_product_inventory"

        # Check columns
        res = await driver.select(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'store_product_inventory'"
        )
        columns = {row["column_name"]: (row["data_type"], row["is_nullable"]) for row in res}

        assert "id" in columns
        assert "store_id" in columns
        assert "product_id" in columns
        assert "quantity_available" in columns
        assert "stock_status" in columns
        assert "pickup_available" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        assert columns["quantity_available"][0] == "integer"
        assert columns["stock_status"][0] == "character varying"
        assert columns["pickup_available"][0] == "boolean"


async def test_vector_indexes():
    from app.config import db, db_manager
    async with db_manager.provide_session(db) as driver:
        res = await driver.select(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('product', 'embedding_cache') AND indexname LIKE '%embedding_idx'"
        )
        assert len(res) == 2
        for row in res:
            assert "USING scann" in row["indexdef"]
            assert "cosine" in row["indexdef"]
