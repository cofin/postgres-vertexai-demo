# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

import pytest
from sqlspec.adapters.asyncpg import AsyncpgDriver

from app.domain.products.services import ProductService

pytestmark = pytest.mark.anyio


async def test_in_db_embeddings_flow(driver: AsyncpgDriver, product_service: ProductService):
    # 1. Clean up existing test product if any
    await driver.execute("DELETE FROM product WHERE sku = 'DB-ML-TEST'")
    await driver.commit()

    # 2. Insert product with NULL embedding
    await driver.execute(
        "INSERT INTO product (name, price, description, sku, in_stock) VALUES (:name, :price, :description, :sku, :in_stock)",
        name="In-Database ML Espresso",
        price=3.99,
        description="A rich espresso shot with crema generated inside the database.",
        sku="DB-ML-TEST",
        in_stock=True,
    )
    await driver.commit()

    # 3. Assert embedding is NULL
    row = await driver.select_one_or_none("SELECT embedding FROM product WHERE sku = 'DB-ML-TEST'")
    assert row is not None
    assert row.get("embedding") is None

    # 4. Trigger backfill via ProductService
    updated = await product_service.backfill_embeddings()
    assert updated > 0

    # 5. Assert embedding is now populated and has 3072 dimensions
    row = await driver.select_one_or_none("SELECT embedding FROM product WHERE sku = 'DB-ML-TEST'")
    assert row is not None
    embedding = row.get("embedding")
    assert embedding is not None
    assert len(embedding) == 3072

    # 6. Test search_by_text_in_db
    results = await product_service.search_by_text_in_db(
        query_text="database espresso",
        similarity_threshold=0.3,
        limit=1,
    )
    assert len(results) > 0
    assert results[0].name == "In-Database ML Espresso"
    assert results[0].similarity_score is not None
    assert results[0].similarity_score > 0.3

    # 7. Clean up
    await driver.execute("DELETE FROM product WHERE sku = 'DB-ML-TEST'")
    await driver.commit()
