# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CLI commands for the coffee shop demo application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click
import structlog
from rich import get_console
from rich.prompt import Prompt
from sqlspec.extensions.litestar.cli import database_group as database_management_group

from app.db.utils import load_fixtures
from app.utils.sync_tools import run_

if TYPE_CHECKING:
    from rich.console import Console


logger = structlog.get_logger()

# Constants
MAX_ERROR_LENGTH = 200
MAX_PHRASE_DISPLAY = 40


def _display_intent_result(console: Console, result: Any) -> None:
    """Display the primary intent classification result."""
    console.print("[bold]Primary Result:[/bold]")
    console.print(f"  Intent: [bold cyan]{result.intent}[/bold cyan]")
    console.print(f"  Confidence: [bold]{result.confidence:.2%}[/bold]")
    console.print(f"  Matched phrase: [dim]{result.exemplar_phrase}[/dim]")
    console.print(f"  Embedding cached: {'✓' if result.embedding_cache_hit else '✗'}")
    console.print(f"  Fallback used: {'✓' if result.fallback_used else '✗'}")
    console.print()


def _display_alternatives(console: Console, alternative_results: list[Any]) -> None:
    """Display alternative intent classification results."""
    if alternative_results:
        from rich.table import Table

        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Intent", style="cyan", width=20)
        table.add_column("Confidence", width=12)
        table.add_column("Threshold", width=12)
        table.add_column("Example Phrase", style="dim", width=50)

        for alt in alternative_results:
            confidence_str = f"{alt.similarity:.1%}"
            threshold_str = f"{alt.confidence_threshold:.1%}"

            if alt.similarity >= alt.confidence_threshold:
                confidence_str = f"[bold green]{confidence_str}[/bold green]"
            else:
                confidence_str = f"[dim]{confidence_str}[/dim]"

            table.add_row(
                alt.intent,
                confidence_str,
                threshold_str,
                alt.phrase[:MAX_PHRASE_DISPLAY] + "..." if len(alt.phrase) > MAX_PHRASE_DISPLAY else alt.phrase,
            )

        console.print("[bold]Alternative Matches:[/bold]")
        console.print(table)
        console.print()


# Fixtures commands
@database_management_group.command(name="load-fixtures", help="Load application fixture data into the database.")  # type: ignore[misc]
@click.option("--tables", "-t", help="Comma-separated list of specific tables to load (loads all if not specified)")
@click.option("--list", "list_fixtures", is_flag=True, help="List available fixture files")
def load_fixtures_cmd(tables: str | None, list_fixtures: bool) -> None:
    """Load application fixture data into the database."""

    if list_fixtures:
        _display_fixture_list()
        return

    _load_fixture_data(tables)


def _display_fixture_list() -> None:
    """Display available fixture files."""
    from pathlib import Path

    from rich.table import Table

    from app.lib.settings import get_settings
    from app.utils.fixtures import FixtureProcessor

    console = get_console()
    console.rule("[bold blue]Available Fixture Files", style="blue", align="left")
    console.print()

    fixtures_dir = Path(get_settings().db.FIXTURE_PATH)
    processor = FixtureProcessor(fixtures_dir)
    fixture_files = processor.get_fixture_files()

    if not fixture_files:
        console.print("[yellow]No fixture files found in fixtures directory[/yellow]")
        return

    table = Table(show_header=True, header_style="bold blue", expand=True)
    table.add_column("Table", style="cyan", ratio=2)
    table.add_column("File", style="dim", ratio=3)
    table.add_column("Records", justify="right", ratio=1)
    table.add_column("Size", justify="right", ratio=1)
    table.add_column("Status", ratio=2)

    for fixture_file in fixture_files:
        table_name = processor.get_table_name(fixture_file.name)
        try:
            data = processor.load_fixture_data(fixture_file)
            records = str(len(data))
            size_bytes = fixture_file.stat().st_size
            size_mb = size_bytes / 1024 / 1024
            size = f"{size_mb:.1f} MB" if size_mb > 1 else f"{size_bytes} B"
            status = "[green]Ready[/green]"
        except (OSError, PermissionError) as e:
            records = "[dim]N/A[/dim]"
            size = "[dim]N/A[/dim]"
            status = f"[red]Error: {e}[/red]"

        table.add_row(table_name, fixture_file.name, records, size, status)

    console.print(table)
    console.print()


def _load_fixture_data(tables: str | None) -> None:
    """Load fixture data into database."""
    console = get_console()
    console.rule("[bold blue]Loading Database Fixtures", style="blue", align="left")
    console.print()

    # Parse tables if provided
    table_list = None
    if tables:
        table_list = [t.strip() for t in tables.split(",")]
        console.print(f"[dim]Loading specific tables: {', '.join(table_list)}[/dim]")
    else:
        console.print("[dim]Loading all available fixtures[/dim]")
    console.print()

    async def _load_fixtures() -> None:
        from app.server.deps import create_service_provider
        from app.services.base import SQLSpecService

        provider = create_service_provider(SQLSpecService)
        service_gen = provider()

        try:
            _service = await anext(service_gen)
            with console.status("[bold yellow]Loading fixtures...", spinner="dots"):
                results = await load_fixtures(table_list)

            if not results:
                console.print("[yellow]No fixture files found to load[/yellow]")
                return

            _display_fixture_results(results)
        finally:
            await service_gen.aclose()

    run_(_load_fixtures)()


def _display_fixture_results(results: dict) -> None:
    """Display fixture loading results."""
    from rich.table import Table

    console = get_console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Table", style="cyan", width=35)
    table.add_column("Status", width=100)

    total_upserted = 0
    total_failed = 0
    total_records = 0

    for table_name, result in results.items():
        row_data = _process_fixture_result(table_name, result)
        table.add_row(row_data["row"][0], row_data["row"][4])  # Only Table and Status columns

        total_upserted += row_data["upserted"]
        total_failed += row_data["failed"]
        total_records += row_data["total"]

    console.print(table)
    console.print()
    _print_fixture_summary(total_upserted, total_failed, total_records)


def _process_fixture_result(table_name: str, result: dict | int | str) -> dict:
    """Process individual fixture result for display."""
    if isinstance(result, dict):
        upserted = result.get("upserted", 0)
        failed = result.get("failed", 0)
        total = result.get("total", 0)
        error = result.get("error")

        status = _get_fixture_status(upserted, failed, error)

        return {
            "row": [
                table_name,
                str(upserted) if upserted > 0 else "[dim]0[/dim]",
                str(failed) if failed > 0 else "[dim]0[/dim]",
                str(total),
                status,
            ],
            "upserted": upserted,
            "failed": failed,
            "total": total,
        }
    if isinstance(result, int):
        # Legacy format
        status = "[green]✓ Success[/green]" if result > 0 else "[yellow]⚠ No new records[/yellow]"
        return {
            "row": [table_name, str(result), "[dim]0[/dim]", "[dim]-[/dim]", status],
            "upserted": result,
            "failed": 0,
            "total": 0,
        }
    # Error case
    status = f"[red]✗ {result}[/red]"
    return {
        "row": [table_name, "[dim]0[/dim]", "[dim]0[/dim]", "[dim]0[/dim]", status],
        "upserted": 0,
        "failed": 0,
        "total": 0,
    }


def _get_fixture_status(upserted: int, failed: int, error: str | None) -> str:
    """Get status text for fixture result."""
    if upserted > 0 and failed == 0:
        return f"[green]✓ {upserted} upserted[/green]"
    if upserted > 0 and failed > 0:
        return f"[yellow]⚠ {upserted} upserted, {failed} failed[/yellow]"
    if failed > 0:
        status = f"[red]✗ {failed} failed[/red]"
        if error:
            # Show more detailed error information
            # Extract PostgreSQL error code if present
            if "[42P01]" in error or ("relation" in error.lower() and "does not exist" in error.lower()):
                status += "\n[dim]PostgreSQL SQL syntax error[/dim]"
                status += "\n[dim][42P01]: Table does not exist[/dim]"
            elif len(error) > MAX_ERROR_LENGTH:
                # Show first part of error with ellipsis
                status += f"\n[dim]{error[:197]}...[/dim]"
            else:
                status += f"\n[dim]{error}[/dim]"
        return status
    return "[dim]Empty fixture[/dim]"


def _print_fixture_summary(total_upserted: int, total_failed: int, total_records: int) -> None:
    """Print fixture loading summary."""
    console = get_console()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  • [green]Upserted: {total_upserted}[/green]")
    if total_failed > 0:
        console.print(f"  • [red]Failed: {total_failed}[/red]")
    console.print(f"  • [dim]Total records in fixtures: {total_records}[/dim]")
    console.print()


@database_management_group.command(name="export-fixtures", help="Export database tables to fixture files.")  # type: ignore[misc]
@click.option(
    "--tables", "-t", help="Comma-separated list of specific tables to export (exports default set if not specified)"
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="Output directory for fixture files (defaults to fixtures directory)",
)
@click.option("--no-compress", is_flag=True, help="Don't gzip compress the output files")
def export_fixtures_cmd(tables: str | None, output_dir: str | None, no_compress: bool) -> None:
    """Export database tables to fixture files."""
    from pathlib import Path

    from rich.table import Table

    console = get_console()

    try:
        console.rule("[bold blue]Exporting Database Fixtures", style="blue", align="left")
        console.print()

        # Parse tables if provided
        table_list = None
        if tables:
            table_list = [t.strip() for t in tables.split(",")]
            console.print(f"[dim]Exporting specific tables: {', '.join(table_list)}[/dim]")
        else:
            console.print("[dim]Exporting default table set[/dim]")

        if output_dir:
            console.print(f"[dim]Output directory: {output_dir}[/dim]")
        else:
            console.print("[dim]Output directory: fixtures directory[/dim]")

        console.print(f"[dim]Compression: {'Disabled' if no_compress else 'Enabled'}[/dim]")
        console.print()

        async def _export_fixtures() -> None:
            from app.db.utils import export_fixtures

            with console.status("[bold yellow]Exporting fixtures...", spinner="dots"):
                output_path = Path(output_dir) if output_dir else None
                results = await export_fixtures(tables=table_list, output_dir=output_path, compress=not no_compress)

            if not results:
                console.print("[yellow]No tables found to export[/yellow]")
                return

            # Display results with dynamic width
            table = Table(show_header=True, header_style="bold blue", expand=True)
            table.add_column("Table", style="cyan", ratio=2)
            table.add_column("Output File", ratio=4)
            table.add_column("Status", ratio=2)

            success_count = 0
            for table_name, result in results.items():
                if result.startswith("Error:"):
                    status = "[red]✗ Failed[/red]"
                    output_file = f"[dim]{result}[/dim]"
                elif result == "No data found":
                    status = "[yellow]⚠ Empty[/yellow]"
                    output_file = "[dim]No data to export[/dim]"
                else:
                    status = "[green]✓ Success[/green]"
                    output_file = f"[cyan]{result}[/cyan]"
                    success_count += 1

                table.add_row(table_name, output_file, status)

            console.print(table)
            console.print()
            console.print(f"[bold green]Successfully exported: {success_count} tables[/bold green]")
            console.print()

        run_(_export_fixtures)()

    except Exception as e:
        console.print(f"\n[red]✗[/red] Error exporting fixtures: [red]{e}[/red]")
        raise click.ClickException(str(e)) from e


# Embedding commands (placeholder - services not implemented yet)
@database_management_group.command(  # type: ignore[misc]
    name="bulk-embed", help="Run bulk embedding job for all products using Vertex AI Batch Prediction."
)
def bulk_embed() -> None:
    """Run bulk embedding job for all products using Vertex AI Batch Prediction."""
    console = get_console()
    console.print("[yellow]⚠ Bulk embedding service not yet implemented.[/yellow]")


@database_management_group.command(  # type: ignore[misc]
    name="embed-new", help="Process new/updated products using online embedding API for real-time updates."
)
@click.option("--limit", default=200, help="Maximum number of products to process in this batch (default: 200)")
def embed_new(limit: int) -> None:
    """Process new/updated products using online embedding API for real-time updates."""
    console = get_console()
    console.rule("[bold blue]Processing Product Embeddings", style="blue", align="left")
    console.print()

    async def _embed_new_products() -> None:
        from app.server.deps import create_service_provider
        from app.services.product import ProductService
        from app.services.vertex_ai import VertexAIService

        # Create service providers
        product_provider = create_service_provider(ProductService)
        product_service_gen = product_provider()

        try:
            product_service = await anext(product_service_gen)
            vertex_ai_service = VertexAIService()

            # Get products without embeddings
            with console.status("[bold yellow]Finding products without embeddings...", spinner="dots"):
                products = await product_service.get_products_without_embeddings(limit)

            if not products:
                console.print("[green]✓ All products already have embeddings![/green]")
                return

            console.print(f"[cyan]Found {len(products)} products without embeddings[/cyan]")
            console.print()

            # Process products in batches
            success_count = 0
            error_count = 0

            with console.status("[bold yellow]Generating embeddings...", spinner="dots") as status:
                for i, product in enumerate(products, 1):
                    try:
                        # Update status
                        status.update(f"[bold yellow]Processing product {i}/{len(products)}: {product.name}...")

                        # Generate embedding for product
                        combined_text = f"{product.name}: {product.description}"
                        embedding = await vertex_ai_service.get_text_embedding(combined_text)

                        # Update product with embedding
                        await product_service.update_product_embedding(product.id, embedding)

                        success_count += 1
                        logger.debug(
                            "Updated product embedding",
                            product_id=product.id,
                            product_name=product.name,
                        )

                    except Exception as e:  # noqa: BLE001
                        error_count += 1
                        logger.warning(
                            "Failed to process product embedding",
                            product_id=product.id,
                            product_name=product.name,
                            error=str(e),
                        )

            # Show results
            console.print(f"[bold green]✓ Successfully processed {success_count} products[/bold green]")
            if error_count > 0:
                console.print(f"[bold red]✗ Failed to process {error_count} products[/bold red]")
            console.print()

        finally:
            await product_service_gen.aclose()

    run_(_embed_new_products)()


@database_management_group.command(name="model-info", help="Show information about currently configured AI models.")  # type: ignore[misc]
def model_info() -> None:
    """Show information about currently configured AI models."""

    def _show_model_info() -> None:
        from app.lib.settings import get_settings
        from app.services.vertex_ai import VertexAIService

        console = get_console()
        console.print("[bold cyan]🤖 AI Model Configuration[/bold cyan]")

        # Show settings
        settings = get_settings()
        console.print(f"[bold]Chat Model:[/bold] {settings.vertex_ai.CHAT_MODEL}")
        console.print(f"[bold]Embedding Model:[/bold] {settings.vertex_ai.EMBEDDING_MODEL}")
        console.print(f"[bold]Google Project:[/bold] {settings.vertex_ai.PROJECT_ID}")
        console.print(f"[bold]Location:[/bold] {settings.vertex_ai.LOCATION}")
        console.print(f"[bold]Embedding Dimensions:[/bold] {settings.vertex_ai.EMBEDDING_DIMENSIONS}")

        # Test model initialization
        console.print("\n[bold cyan]🔍 Testing Model Initialization...[/bold cyan]")
        try:
            VertexAIService()
            console.print("[bold green]✓ Successfully initialized![/bold green]")
            console.print(f"[bold]Chat Model:[/bold] {settings.vertex_ai.CHAT_MODEL}")
            console.print(f"[bold]Embedding Model:[/bold] {settings.vertex_ai.EMBEDDING_MODEL}")

        except Exception as e:  # noqa: BLE001
            console.print(f"[bold red]✗ Model initialization failed: {e}[/bold red]")

    _show_model_info()


# Data commands
@database_management_group.command(name="truncate-tables", help="Clear all tables in the database.")  # type: ignore[misc]
@click.option(
    "--skip-cache",
    is_flag=True,
    help="Skip cache tables (response_cache, search_metrics, embedding_cache)",
)
@click.option(
    "--skip-session",
    is_flag=True,
    help="Skip session tables (chat_session, chat_conversation)",
)
@click.option(
    "--skip-data",
    is_flag=True,
    help="Skip data tables (products)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def truncate_tables(
    skip_cache: bool,
    skip_session: bool,
    skip_data: bool,
    force: bool,
) -> None:
    """Clear all tables in the database."""
    console = get_console()

    # Get tables to truncate
    tables = _get_tables_to_truncate(skip_cache, skip_session, skip_data)
    if not tables:
        console.print("[yellow]No tables selected for truncation. Use --help to see options.[/yellow]")
        return

    # Show tables and confirm
    _display_tables(console, tables)
    if not force and not _confirm_truncate(console):
        return

    async def _truncate_tables() -> None:
        """Truncate tables."""
        from app.config import db

        console.print("[bold cyan]Truncating tables...[/bold cyan]")

        async with db.provide_session() as session:
            for table_name in tables:
                # Validate table name
                valid_tables = [
                    "response_cache",
                    "search_metrics",
                    "embedding_cache",
                    "chat_conversation",
                    "chat_session",
                    "products",
                ]
                if table_name not in valid_tables:
                    console.print(f"[red]✗ Invalid table name: {table_name}[/red]")
                    continue

                try:
                    console.print(f"[cyan]Clearing {table_name}...[/cyan]")
                    # Use DELETE instead of TRUNCATE for safety
                    await session.execute(f"DELETE FROM {table_name}")  # noqa: S608
                    console.print(f"[green]✓ Cleared {table_name}[/green]")
                except Exception as e:  # noqa: BLE001
                    console.print(f"[red]✗ Failed to clear {table_name}: {e}[/red]")
            await session.commit()
            console.print("\n[bold green]Table clearing complete![/bold green]")

    run_(_truncate_tables)()


def _get_tables_to_truncate(skip_cache: bool, skip_session: bool, skip_data: bool) -> list[str]:
    """Get list of tables to truncate based on flags."""
    cache_tables = ["response_cache", "search_metrics", "embedding_cache"]
    session_tables = ["chat_conversation", "chat_session"]  # Order matters for FKs
    data_tables = ["products"]  # Order matters for FKs

    tables = []
    if not skip_cache:
        tables.extend(cache_tables)
    if not skip_session:
        tables.extend(session_tables)
    if not skip_data:
        tables.extend(data_tables)
    return tables


def _display_tables(console: Console, tables: list[str]) -> None:
    """Display tables that will be truncated."""
    console.print("[bold]Tables to truncate:[/bold]")
    for table in tables:
        console.print(f"  • {table}")


def _confirm_truncate(console: Console) -> bool:
    """Confirm truncation with user."""
    console.print("\n[bold red]⚠️  WARNING: This will remove ALL data from the selected tables![/bold red]")
    confirm = Prompt.ask(
        "[bold red]Are you absolutely sure?[/bold red]",
        choices=["y", "n"],
        default="n",
    )
    if confirm.lower() != "y":
        console.print("[yellow]Operation cancelled.[/yellow]")
        return False
    return True


@database_management_group.command(name="dump-data", help="Export database tables to JSON files.")  # type: ignore[misc]
@click.option(
    "--table",
    "-t",
    default="*",
    help="Table name to export, or '*' for all tables",
)
@click.option(
    "--path",
    "-p",
    default="app/db/fixtures",
    help="Directory to export to",
)
@click.option(
    "--no-compress",
    is_flag=True,
    help="Export uncompressed JSON (default is gzipped)",
)
def dump_data(table: str, path: str, no_compress: bool) -> None:
    """Export database tables to JSON files."""
    from pathlib import Path

    from app.db.utils import export_fixtures

    async def _dump_data() -> None:
        console = get_console()
        table_list = None if table == "*" else [table]
        export_path = Path(path)

        console.print(f"[bold cyan]📤 Exporting{'all tables' if table == '*' else f' table {table}'}...[/bold cyan]")
        console.print(f"Export path: {export_path}")
        console.print(f"Compression: {'disabled' if no_compress else 'enabled'}")

        try:
            results = await export_fixtures(table_list, export_path, compress=not no_compress)
            console.print("[bold green]✓ Export completed![/bold green]")
            for table_name, result in results.items():
                console.print(f"  ✓ {table_name}: {result}")
        except Exception as e:  # noqa: BLE001
            console.print(f"[bold red]✗ Export failed: {e}[/bold red]")

    run_(_dump_data)()


# Intent management commands
@database_management_group.command(name="populate-intents", help="Populate intent exemplars with embeddings.")  # type: ignore[misc]
@click.option("--force", "-f", is_flag=True, help="Force repopulation of existing exemplars")
@click.option("--intent", "-i", help="Populate only specific intent (optional)")
def populate_intents(force: bool, intent: str | None) -> None:
    """Populate intent exemplars with embeddings."""

    async def _populate_intents() -> None:
        from app.lib.intents import INTENT_EXEMPLARS
        from app.server.deps import create_service_provider
        from app.services.exemplar import ExemplarService
        from app.services.vertex_ai import VertexAIService

        console = get_console()
        console.rule("[bold blue]Populating Intent Exemplars", style="blue", align="left")
        console.print()

        # Filter intents if specified
        exemplars_to_load = INTENT_EXEMPLARS
        if intent:
            if intent in INTENT_EXEMPLARS:
                exemplars_to_load = {intent: INTENT_EXEMPLARS[intent]}
                console.print(f"[dim]Loading exemplars for intent: {intent}[/dim]")
            else:
                console.print(f"[red]Error: Intent '{intent}' not found in configuration[/red]")
                return
        else:
            console.print("[dim]Loading exemplars for all intents[/dim]")
        console.print()

        provider = create_service_provider(ExemplarService)
        service_gen = provider()

        try:
            exemplar_service = await anext(service_gen)
            vertex_ai_service = VertexAIService()

            with console.status("[bold yellow]Loading intent exemplars...", spinner="dots"):
                count = await exemplar_service.load_exemplars_bulk(
                    exemplars_to_load,
                    vertex_ai_service,
                    default_threshold=0.7,
                )

            console.print(f"[bold green]✓ Successfully populated {count} intent exemplars![/bold green]")

            # Show stats
            stats = await exemplar_service.get_intent_stats()
            console.print(f"Total exemplars in database: {stats.total_exemplars}")
            console.print(f"Number of intents: {stats.intents_count}")
            console.print(f"Average usage per exemplar: {stats.average_usage:.1f}")

        finally:
            await service_gen.aclose()

    run_(_populate_intents)()


@database_management_group.command(name="test-intent", help="Test intent classification for a query.")  # type: ignore[misc]
@click.argument("query", required=True)
@click.option("--alternatives", "-a", is_flag=True, help="Show alternative intent matches")
def test_intent(query: str, alternatives: bool) -> None:
    """Test intent classification for a query."""

    async def _test_intent() -> None:
        from app.server.deps import create_service_provider
        from app.services.exemplar import ExemplarService
        from app.services.intent import IntentService
        from app.services.vertex_ai import VertexAIService

        console = get_console()
        console.rule("[bold blue]Testing Intent Classification", style="blue", align="left")
        console.print()
        console.print(f"Query: [cyan]{query}[/cyan]")
        console.print()

        provider = create_service_provider(ExemplarService)
        service_gen = provider()

        try:
            exemplar_service = await anext(service_gen)
            vertex_ai_service = VertexAIService()
            intent_service = IntentService(
                exemplar_service.driver,
                exemplar_service,
                vertex_ai_service,
            )

            with console.status("[bold yellow]Classifying intent...", spinner="dots"):
                if alternatives:
                    result, alternative_results = await intent_service.classify_intent_with_alternatives(query)
                else:
                    result = await intent_service.classify_intent(query)
                    alternative_results = []

            # Display results using helper functions
            _display_intent_result(console, result)

            if alternatives:
                _display_alternatives(console, alternative_results)

        finally:
            await service_gen.aclose()

    run_(_test_intent)()


@database_management_group.command(name="intent-stats", help="Show intent classification statistics.")  # type: ignore[misc]
def intent_stats() -> None:
    """Show intent classification statistics."""

    async def _intent_stats() -> None:
        from rich.table import Table

        from app.server.deps import create_service_provider
        from app.services.exemplar import ExemplarService

        console = get_console()
        console.rule("[bold blue]Intent Classification Statistics", style="blue", align="left")
        console.print()

        provider = create_service_provider(ExemplarService)
        service_gen = provider()

        try:
            exemplar_service = await anext(service_gen)

            stats = await exemplar_service.get_intent_stats()

            # Overall stats
            console.print("[bold]Overall Statistics:[/bold]")
            console.print(f"  Total exemplars: [cyan]{stats.total_exemplars}[/cyan]")
            console.print(f"  Number of intents: [cyan]{stats.intents_count}[/cyan]")
            console.print(f"  Average usage: [cyan]{stats.average_usage:.1f}[/cyan]")
            console.print()

            # Top intents table
            if stats.top_intents:
                table = Table(show_header=True, header_style="bold blue")
                table.add_column("Intent", style="cyan", width=25)
                table.add_column("Exemplars", justify="right", width=12)
                table.add_column("Total Usage", justify="right", width=12)
                table.add_column("Avg Threshold", justify="right", width=15)

                for intent_data in stats.top_intents:
                    table.add_row(
                        intent_data["intent"],
                        str(intent_data["exemplar_count"]),
                        str(intent_data["total_usage"]),
                        f"{intent_data['avg_threshold']:.2%}",
                    )

                console.print("[bold]Intent Breakdown:[/bold]")
                console.print(table)
                console.print()

        finally:
            await service_gen.aclose()

    run_(_intent_stats)()


@database_management_group.command(name="clear-intents", help="Clear intent exemplar cache.")  # type: ignore[misc]
@click.option("--intent", "-i", help="Clear only specific intent (optional)")
@click.option("--unused-only", is_flag=True, help="Clear only unused exemplars")
def clear_intents(intent: str | None, unused_only: bool) -> None:
    """Clear intent exemplar cache."""

    async def _clear_intents() -> None:
        from app.server.deps import create_service_provider
        from app.services.exemplar import ExemplarService

        console = get_console()

        if unused_only:
            console.rule("[bold yellow]Clearing Unused Intent Exemplars", style="yellow", align="left")
        elif intent:
            console.rule(f"[bold yellow]Clearing Intent: {intent}", style="yellow", align="left")
        else:
            console.rule("[bold red]Clearing All Intent Exemplars", style="red", align="left")

        console.print()

        # Confirm if clearing all
        if not intent and not unused_only:
            console.print("[bold red]⚠️  WARNING: This will remove ALL intent exemplars![/bold red]")
            from rich.prompt import Prompt

            confirm = Prompt.ask(
                "[bold red]Are you absolutely sure?[/bold red]",
                choices=["y", "n"],
                default="n",
            )
            if confirm.lower() != "y":
                console.print("[yellow]Operation cancelled.[/yellow]")
                return

        provider = create_service_provider(ExemplarService)
        service_gen = provider()

        try:
            exemplar_service = await anext(service_gen)

            with console.status("[bold yellow]Clearing intent exemplars...", spinner="dots"):
                if unused_only:
                    deleted_count = await exemplar_service.clean_unused_exemplars()
                    console.print(f"[green]✓ Cleared {deleted_count} unused exemplars[/green]")
                elif intent:
                    # Get exemplars for the intent first
                    exemplars = await exemplar_service.get_exemplars_by_intent(intent)
                    for exemplar in exemplars:
                        await exemplar_service.delete_exemplar(exemplar.id)
                    console.print(f"[green]✓ Cleared {len(exemplars)} exemplars for intent '{intent}'[/green]")
                else:
                    # Clear all intent exemplars
                    await exemplar_service.driver.execute("DELETE FROM intent_exemplar")
                    console.print("[green]✓ Cleared all intent exemplars[/green]")

        finally:
            await service_gen.aclose()

    run_(_clear_intents)()


@database_management_group.command(
    name="rebuild-vector-indexes", help="Drop and recreate vector indexes for embeddings."
)  # type: ignore[misc]
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def rebuild_vector_indexes(force: bool) -> None:
    """Drop and recreate vector indexes for embeddings.

    This rebuilds the IVFFlat indexes for product embeddings and intent exemplar embeddings.
    Useful after loading new fixtures or when vector search performance degrades.
    """
    console = get_console()

    # Confirm operation unless forced
    if not force:
        console.print("[bold red]⚠️  WARNING: This will temporarily drop vector indexes![/bold red]")
        console.print("Vector searches may be slow during index rebuild.")
        from rich.prompt import Prompt

        confirm = Prompt.ask(
            "\n[bold red]Continue with rebuild?[/bold red]",
            choices=["y", "n"],
            default="n",
        )
        if confirm.lower() != "y":
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    async def _rebuild_vector_indexes() -> None:
        """Rebuild vector indexes."""
        from app.config import db

        console.rule("[bold blue]Rebuilding Vector Indexes", style="blue", align="left")
        console.print()

        vector_indexes = [
            {
                "name": "product_embedding_ivfflat_idx",
                "table": "product",
                "column": "embedding",
                "create_sql": "CREATE INDEX product_embedding_ivfflat_idx ON product USING ivfflat (embedding vector_cosine_ops)",
            },
            {
                "name": "intent_exemplar_embedding_ivfflat_idx",
                "table": "intent_exemplar",
                "column": "embedding",
                "create_sql": "CREATE INDEX intent_exemplar_embedding_ivfflat_idx ON intent_exemplar USING ivfflat (embedding vector_cosine_ops)",
            },
        ]

        async with db.provide_session() as session:
            for index_info in vector_indexes:
                index_name = index_info["name"]
                _table_name = index_info["table"]
                create_sql = index_info["create_sql"]

                try:
                    # Drop existing index if it exists
                    console.print(f"[yellow]Dropping index {index_name}...[/yellow]")
                    await session.execute(f"DROP INDEX IF EXISTS {index_name}")

                    # Recreate the index
                    console.print(f"[cyan]Creating index {index_name}...[/cyan]")
                    await session.execute(create_sql)

                    console.print(f"[green]✓ Successfully rebuilt {index_name}[/green]")

                except Exception as e:  # noqa: BLE001
                    console.print(f"[red]✗ Failed to rebuild {index_name}: {e}[/red]")

            await session.commit()

        console.print()
        console.print("[bold green]Vector index rebuild complete![/bold green]")

    run_(_rebuild_vector_indexes)()
