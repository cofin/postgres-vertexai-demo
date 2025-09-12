"""Coffee shop specific fixture management utilities."""

from __future__ import annotations

from pathlib import Path

from app.lib.settings import get_settings
from app.utils.fixtures import FixtureExporter, FixtureLoader

# Table loading order - tables with no dependencies first, then ordered by dependencies
COFFEE_SHOP_TABLES = [
    # Core tables without dependencies
    "products",
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
        return await loader.load_all_fixtures(tables)
    finally:
        await service_gen.aclose()


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
