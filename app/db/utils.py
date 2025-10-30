"""Database utilities using generic fixture infrastructure."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.config import db, db_manager
from app.lib.settings import get_settings
from app.utils.fixtures import FixtureExporter, FixtureLoader

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase


# Coffee shop table loading order (respects foreign key dependencies)
COFFEE_SHOP_TABLES = [
    "store",
    "product",
    "intent_exemplar",
]


async def load_fixtures(tables: list[str] | None = None) -> dict[str, dict | str]:
    """Load fixture data into database using generic loader.

    Args:
        tables: Optional list of specific tables to load

    Returns:
        Dictionary mapping table names to loading results
    """
    async with db_manager.provide_session(db) as driver:
        settings = get_settings()
        fixtures_dir = Path(settings.db.FIXTURE_PATH)

        loader = FixtureLoader(
            fixtures_dir=fixtures_dir,
            driver=driver,
            table_order=COFFEE_SHOP_TABLES,
        )

        results = await loader.load_all_fixtures(specific_tables=tables)

        # Reset sequences for database tables to avoid duplicate key issues
        await _reset_sequences(driver)

        return results


async def _reset_sequences(driver: AsyncDriverAdapterBase) -> None:
    """Reset PostgreSQL sequences to match the current maximum IDs in tables.

    Queries the data dictionary to find all sequences owned by table columns,
    then resets each sequence to match the current max value in its table.
    This prevents duplicate key violations when inserting new records after
    loading fixtures with explicit IDs.
    """
    import contextlib

    # Query PostgreSQL data dictionary to find all sequences and their owner tables/columns
    sequences = await driver.select(
        """
        SELECT
            s.relname AS sequence_name,
            t.relname AS table_name,
            a.attname AS column_name
        FROM pg_class s
        JOIN pg_depend d ON d.objid = s.oid
        JOIN pg_class t ON d.refobjid = t.oid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
        WHERE s.relkind = 'S'
        AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """
    )

    # Reset each sequence to the max value of its column
    for seq in sequences:
        table_name = seq["table_name"]
        column_name = seq["column_name"]
        sequence_name = seq["sequence_name"]

        with contextlib.suppress(Exception):
            # Use COALESCE to handle empty tables (returns 1 if table is empty)
            await driver.execute(
                f"SELECT setval('{sequence_name}', (SELECT COALESCE(MAX({column_name}), 1) FROM {table_name}));"
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
    async with db_manager.provide_session(db) as driver:
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
