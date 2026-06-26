# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""CLI commands for PostgreSQL health checking."""

from __future__ import annotations

import rich_click as click
from rich.console import Console

from tools.postgres.health import HealthChecker

console = Console()


@click.command(name="health")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed health information")
def health_command(verbose: bool) -> None:
    """Check health of PostgreSQL deployment.

    Performs comprehensive health checks including:
    - Container runtime availability (Docker/Podman)
    - Database container status
    - PostgreSQL connectivity
    - psql CLI availability (optional)

    Examples:
        # Basic health check
        python manage.py database postgres health

        # Detailed health check
        python manage.py database postgres health --verbose
    """
    try:
        checker = HealthChecker(console=console)
        health = checker.check_all(verbose=verbose)
        checker.display_health(health, verbose=verbose)

        # Exit with error code if unhealthy
        if not health.is_healthy:
            raise click.Abort

    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        raise click.Abort from e
