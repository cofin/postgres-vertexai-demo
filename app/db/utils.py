"""Coffee shop specific fixture management utilities."""

from __future__ import annotations

from pathlib import Path

from app.lib.settings import get_settings
from app.utils.fixtures import FixtureExporter, FixtureLoader

# Table loading order - tables with no dependencies first, then ordered by dependencies
COFFEE_SHOP_TABLES = [
    # Core tables without dependencies
    "product",
    # Session and user-related tables
    "chat_session",
    "chat_conversation",
    # Caching tables
    "response_cache",
    "embedding_cache",
    # Metrics and analytics
    "search_metrics",
]


async def load_fixtures(tables: list[str] | None = None) -> dict[str, dict[str, str] | str]:
    """Convenience function to load coffee shop fixtures.

    Args:
        tables: Optional list of specific tables to load

    Returns:
        Loading results
    """
    from app.server.deps import create_service_provider
    from app.services.base import SQLSpecService

    # Create a temporary service provider to get a driver
    provider = create_service_provider(SQLSpecService)

    # Use the provider properly to avoid async generator issues
    service_gen = provider()
    try:
        service = await anext(service_gen)
        fixtures_dir = Path(get_settings().db.FIXTURE_PATH)
        loader = FixtureLoader(fixtures_dir=fixtures_dir, driver=service.driver, table_order=COFFEE_SHOP_TABLES)
        results = await loader.load_all_fixtures(tables)

        # Reset sequences for tables with serial primary keys to avoid duplicate key issues
        # This ensures sequences are synced with the max ID after loading fixtures with explicit IDs
        await _reset_sequences(service.driver)

        return results
    finally:
        await service_gen.aclose()


async def _reset_sequences(driver) -> None:
    """Reset PostgreSQL sequences to match the current maximum IDs in tables.

    This prevents duplicate key violations when inserting new records after
    loading fixtures with explicit IDs.
    """
    # Tables with serial primary keys that need sequence reset
    tables_with_sequences = [
        "product",
        "chat_session",
        "chat_conversation",
        "response_cache",
        "embedding_cache",
        "intent_exemplar",
        "search_metrics"
    ]

    for table in tables_with_sequences:
        # Reset sequence to max(id) + 1 for each table
        sequence_name = f"{table}_id_seq"
        reset_query = f"SELECT setval('{sequence_name}', (SELECT COALESCE(MAX(id), 1) FROM {table}));"
        try:
            await driver.execute(reset_query)
        except Exception:
            # Ignore errors for tables that don't exist or don't have sequences
            pass


async def export_fixtures(
    tables: list[str] | None = None, output_dir: Path | None = None, compress: bool = True
) -> dict[str, str]:
    """Convenience function to export coffee shop fixtures.

    Args:
        tables: Optional list of specific tables to export
        output_dir: Output directory (defaults to fixtures dir)
        compress: Whether to gzip compress output

    Returns:
        Export results
    """
    from app.server.deps import create_service_provider
    from app.services.base import SQLSpecService

    # Create a temporary service provider to get a driver
    provider = create_service_provider(SQLSpecService)

    # Use the provider properly to avoid async generator issues
    service_gen = provider()
    try:
        service = await anext(service_gen)
        fixtures_dir = Path(get_settings().db.FIXTURE_PATH)
        exporter = FixtureExporter(fixtures_dir=fixtures_dir, driver=service.driver, table_order=COFFEE_SHOP_TABLES)
        return await exporter.export_all_fixtures(tables, output_dir, compress)
    finally:
        await service_gen.aclose()
