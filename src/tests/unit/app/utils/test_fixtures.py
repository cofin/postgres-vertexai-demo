# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for PostgreSQL fixture processor and loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.utils.fixtures import FixtureLoader, FixtureProcessor


class _CaptureTransaction:
    async def __aenter__(self) -> _CaptureTransaction:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class _CaptureConnection:
    def transaction(self) -> _CaptureTransaction:
        return _CaptureTransaction()


class _CaptureDriver:
    """Async driver double that records the SQL and data passed to ``execute_many``."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.connection = _CaptureConnection()

    async def execute_many(self, statement: str, data: list[tuple[Any, ...]]) -> None:
        self.statements.append((statement, data))

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_postgres_upsert_renders_on_conflict() -> None:
    driver = _CaptureDriver()
    loader = FixtureLoader(fixtures_dir=Path("/tmp"), driver=driver, table_order=["product"])

    # Mock get_fixture_files and load_fixture_data
    original_get_files = loader.processor.get_fixture_files
    original_load_data = loader.processor.load_fixture_data

    loader.processor.get_fixture_files = lambda order: [Path("/tmp/product.json")]
    loader.processor.load_fixture_data = lambda path: [
        {"id": 1, "name": "Midnight Brew", "price": 9.99, "in_stock": True}
    ]

    try:
        results = await loader.load_all_fixtures()
        assert "product" in results
        assert results["product"] == {"upserted": 1, "failed": 0, "total": 1}
    finally:
        loader.processor.get_fixture_files = original_get_files
        loader.processor.load_fixture_data = original_load_data

    assert driver.statements, "FixtureLoader must execute a statement"
    sql, data = driver.statements[0]

    sql_lower = sql.strip().lower()
    assert 'insert into "product"' in sql_lower
    assert "on conflict (id) do update set" in sql_lower
    assert '"name" = excluded."name"' in sql_lower
    assert '"price" = excluded."price"' in sql_lower
    assert '"in_stock" = excluded."in_stock"' in sql_lower


def test_prepare_record_preserves_booleans_and_converts_embeddings() -> None:
    processor = FixtureProcessor(Path("/tmp"))

    # Test boolean preservation and embedding conversion
    prepared = processor.prepare_record(
        {
            "id": 1,
            "in_stock": True,
            "pickup_available": False,
            "embedding": "[0.1, 0.2, 0.3]",
        }
    )

    assert prepared["in_stock"] is True
    assert prepared["pickup_available"] is False
    assert prepared["embedding"] == [0.1, 0.2, 0.3]


def test_prepare_record_handles_comma_separated_embeddings() -> None:
    processor = FixtureProcessor(Path("/tmp"))
    prepared = processor.prepare_record({"embedding": "0.1, 0.2, 0.3"})
    assert prepared["embedding"] == [0.1, 0.2, 0.3]
