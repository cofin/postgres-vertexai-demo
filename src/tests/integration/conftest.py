# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from litestar.testing import AsyncTestClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable

    from litestar import Litestar
    from sqlspec.adapters.asyncpg import AsyncpgDriver

    from app.domain.products.services import ProductService
    from app.domain.system.services import CacheService


_ORACLE_SCHEMA_READY = False
_ORACLE_SEED_DATA_READY = False


# Pin every integration test in this directory to a single xdist worker. The
# Oracle connection pool + fixture-loaded data are shared mutable state; running
# them across two workers causes pool-handle errors and TRUNCATE races.
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config  # unused
    marker = pytest.mark.xdist_group(name="oracle_integration")
    for item in items:
        item.add_marker(marker)


# Removed _bootstrap_test_schema


async def _ensure_postgres_schema(session: AsyncpgDriver) -> None:
    """Idempotent schema check. Assumes migrations are applied externally."""
    global _ORACLE_SCHEMA_READY  # Keep name for now

    if _ORACLE_SCHEMA_READY:
        return
    _ORACLE_SCHEMA_READY = True


async def _mock_database_ml_functions(session: AsyncpgDriver) -> None:
    """Mock the database-side ML functions for local testing without external calls."""
    await session.execute("CREATE SCHEMA IF NOT EXISTS google_ml")
    await session.execute(
        """
        CREATE OR REPLACE FUNCTION google_ml.embedding(model_id VARCHAR, content TEXT)
        RETURNS REAL[]
        LANGUAGE plpgsql
        AS $$
        DECLARE
            dim INT := 3072;
            arr REAL[];
        BEGIN
            SELECT array_agg(0.1::REAL) FROM generate_series(1, dim) INTO arr;
            RETURN arr;
        END;
        $$;
        """
    )
    await session.commit()


async def _ensure_oracle_seed_data(session: AsyncpgDriver) -> None:
    """Load deterministic fixture data once per pytest worker."""
    global _ORACLE_SEED_DATA_READY  # noqa: PLW0603

    if _ORACLE_SEED_DATA_READY:
        return
    await _truncate_fixture_tables(session)
    await _load_app_fixtures(session)
    await _mock_database_ml_functions(session)
    for table in ("product", "store", "store_product_inventory"):
        await session.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(max(id), 1)) FROM {table}"
        )
    await session.commit()
    _ORACLE_SEED_DATA_READY = True


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Create test client."""
    async with AsyncTestClient(app=app) as c:
        yield c


@pytest.fixture
def app() -> Litestar:
    """Create test app instance."""
    from app.config import _reset

    _reset()

    from app.server.asgi import create_app

    return create_app()


async def _truncate_fixture_tables(session: AsyncpgDriver) -> None:
    """Wipe fixture-managed tables so each test session starts from a known state.

    Uses DELETE FROM instead of TRUNCATE TABLE to avoid ScaNN index rebuild
    precondition errors (which require 10k rows during TRUNCATE).
    """
    await session.execute("DELETE FROM store_product_inventory")
    await session.execute("DELETE FROM product")
    await session.execute("DELETE FROM store")
    await session.commit()


async def _load_app_fixtures(session: AsyncpgDriver) -> None:
    """Load the checked-in ``.json.gz`` fixtures into the test database via ``FixtureLoader``."""
    from app.db.utils import COFFEE_SHOP_TABLES
    from app.lib.settings import get_settings
    from app.utils.fixtures import FixtureLoader

    settings = get_settings()
    fixtures_dir = Path(settings.db.FIXTURE_PATH)
    if not await asyncio.to_thread(fixtures_dir.exists):
        return
    loader = FixtureLoader(fixtures_dir=fixtures_dir, driver=session, table_order=COFFEE_SHOP_TABLES)
    await loader.load_all_fixtures()


@pytest.fixture
def unique_test_id() -> str:
    """Return a stable unique suffix for one integration test."""
    return uuid.uuid4().hex


@pytest.fixture
async def oracle_seed_data() -> None:
    """Ensure shared Oracle schema and fixture data are ready for this worker.

    The repo-managed Oracle container and migrations must already be available.
    This fixture only performs expensive DDL/truncate/fixture loading once per
    pytest worker; function-scoped driver sessions depend on the prepared data.
    """
    from app.config import db, db_manager

    try:
        async with db_manager.provide_session(db) as session:
            await _ensure_postgres_schema(session)
            await _ensure_oracle_seed_data(session)
    finally:
        # pytest-anyio creates a fresh event loop per test by default.
        # Closing the shared pool avoids loop-bound pool reuse across tests.
        with contextlib.suppress(Exception):
            await db.close_pool()


@pytest.fixture
async def driver(oracle_seed_data: None) -> AsyncGenerator[AsyncpgDriver, None]:
    """Provide an isolated SQLSpec driver session against shared seeded data.

    The setup pipeline prepares deterministic data once per worker:

        1. Bootstrap schema (idempotent CREATE TABLE)
        2. Truncate fixture-owned tables once
        3. Load .json.gz fixtures once
        4. Insert the SEED-SKU-001 marker once

    Tests that mutate shared app tables should use unique identifiers and
    explicit cleanup fixtures instead of relying on suite-wide truncation.
    """
    from app.config import db, db_manager

    with contextlib.suppress(Exception):
        await db.close_pool()

    try:
        async with db_manager.provide_session(db) as session:
            yield session
    finally:
        # pytest-anyio creates a fresh event loop per test by default.
        # Closing the shared pool avoids loop-bound pool reuse across tests.
        with contextlib.suppress(Exception):
            await db.close_pool()


@pytest.fixture
async def tracked_product_skus(driver: AsyncpgDriver) -> AsyncGenerator[Callable[[str], None], None]:
    """Track product SKUs inserted by a test and delete them afterwards."""
    skus: list[str] = []

    def track(sku: str) -> None:
        skus.append(sku)

    try:
        yield track
    finally:
        for sku in skus:
            with contextlib.suppress(Exception):
                await driver.execute("DELETE FROM product WHERE sku = :sku", sku=sku)
        if skus:
            with contextlib.suppress(Exception):
                await driver.commit()


@pytest.fixture
async def product_service(driver: AsyncpgDriver) -> ProductService:
    """Provide ProductService for testing."""
    from app.domain.products.services import ProductService

    return ProductService(driver)


@pytest.fixture
async def cache_service(driver: AsyncpgDriver) -> CacheService:
    """Provide CacheService for testing."""
    from app.domain.system.services import CacheService

    return CacheService(driver)


@pytest.fixture(autouse=True)
async def _cleanup_db_pool() -> AsyncIterator[None]:
    """Ensure database connection pool is closed and configuration is reset after each test."""
    yield
    from app.config import _reset, db
    try:
        await db.close_pool()
    except Exception as e:  # noqa: BLE001
        print(f"Warning: failed to close database pool during test cleanup: {e}")  # noqa: T201
    finally:
        _reset()
