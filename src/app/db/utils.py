# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Database utilities using generic fixture infrastructure."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import app.config
from app.lib.settings import get_settings
from app.utils.fixtures import FixtureExporter, FixtureLoader

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase


# Coffee shop table loading order (respects foreign key dependencies)
COFFEE_SHOP_TABLES = [
    "store",
    "product",
    "store_product_inventory",
]


async def load_fixtures(tables: list[str] | None = None) -> dict[str, dict | str]:
    """Load fixture data into database using generic loader.

    Args:
        tables: Optional list of specific tables to load

    Returns:
        Dictionary mapping table names to loading results
    """
    async with app.config.db_manager.provide_session(app.config.db) as driver:
        settings = get_settings()
        fixtures_dir = Path(settings.db.FIXTURE_PATH)

        loader = FixtureLoader(fixtures_dir=fixtures_dir, driver=driver, table_order=COFFEE_SHOP_TABLES)
        results = await loader.load_all_fixtures(specific_tables=tables)
        await _reset_sequences(driver)
        return results


async def _reset_sequences(driver: AsyncDriverAdapterBase) -> None:
    """Reset PostgreSQL serial/identity sequences to match the current maximum IDs in tables.

    This prevents duplicate key violations when inserting new records after
    fixtures with explicit IDs are loaded.
    """
    import contextlib

    # Tables with serial columns that need sequence reset
    tables_with_identity = [
        "product",
        "store",
        "store_product_inventory",
        "response_cache",
        "embedding_cache",
        "search_metric",
    ]

    for table in tables_with_identity:
        with contextlib.suppress(Exception):
            await driver.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(max(id), 1)) FROM {table}"
            )


async def export_fixtures(
    tables: list[str] | None = None,
    output_dir: Path | None = None,
    compress: bool = True,
) -> dict[str, str]:
    """Export database tables to fixture files.

    Args:
        tables: Optional list of specific tables to export
        output_dir: Output directory (defaults to fixtures dir)
        compress: Whether to gzip compress output

    Returns:
        Dictionary mapping table names to output paths or error messages
    """

    # Use SQLSpec session directly
    async with app.config.db_manager.provide_session(app.config.db) as driver:
        settings = get_settings()
        fixtures_dir = Path(settings.db.FIXTURE_PATH)

        if output_dir is None:
            output_dir = fixtures_dir

        exporter = FixtureExporter(
            fixtures_dir=fixtures_dir,
            driver=driver,
            table_order=COFFEE_SHOP_TABLES,
        )

        return await exporter.export_all_fixtures(
            tables=tables,
            output_dir=output_dir,
            compress=compress,
        )
