"""PostgreSQL/AlloyDB database container lifecycle management.

This module manages PostgreSQL/AlloyDB Omni container deployment and operations.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from tools.lib.container import ContainerRuntime


@dataclass
class DatabaseConfig:
    """Configuration for PostgreSQL/AlloyDB database container."""

    # Container settings
    container_name: str = "cymbal_coffee_pg-db-1"
    image: str = "google/alloydbomni:latest"
    hostname: str = "db"

    # Port mapping
    host_port: int = 15432
    container_port: int = 5432

    # Environment variables
    postgres_password: str = "super-secret"  # noqa: S105
    postgres_user: str = "app"
    postgres_db: str = "app"

    # Volumes
    data_volume_name: str = "postgres-db-data"

    # Logging
    log_max_size: str = "10m"
    log_max_file: str = "3"

    # Health check
    health_interval: int = 10  # seconds
    health_timeout: int = 5  # seconds
    health_retries: int = 10

    # Restart policy
    restart_policy: str = "unless-stopped"

    # Shared memory and ML flags
    shm_size: str = "1g"
    enable_ml: bool = True
    private_key_path: str | None = None
    resolved_private_key_path: str | None = None

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        """Create configuration from environment variables.

        Reads from:
        - DATABASE_PORT (default: 15432)
        - DATABASE_PASSWORD (default: super-secret)
        - DATABASE_USER (default: app)
        - DATABASE_NAME (default: app)
        - GOOGLE_APPLICATION_CREDENTIALS (default: None)

        Returns:
            DatabaseConfig: Configuration instance
        """
        from dotenv import load_dotenv
        load_dotenv()

        # Expand nested environment variables containing '$'
        for k, v in list(os.environ.items()):
            if "$" in v:
                os.environ[k] = os.path.expandvars(v)

        return cls(
            host_port=int(os.getenv("DATABASE_PORT", "15432")),
            postgres_password=os.getenv("DATABASE_PASSWORD", "super-secret"),
            postgres_user=os.getenv("DATABASE_USER", "app"),
            postgres_db=os.getenv("DATABASE_NAME", "app"),
            private_key_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        )


class PostgreSQLDatabase:
    """Manage PostgreSQL/AlloyDB Omni database container lifecycle."""

    def __init__(
        self,
        runtime: ContainerRuntime,
        config: DatabaseConfig | None = None,
        console: Console | None = None,
    ) -> None:
        """Initialize PostgreSQL database manager.

        Args:
            runtime: Container runtime instance
            config: Database configuration (uses defaults if None)
            console: Rich console for output (creates new if None)
        """
        self.runtime = runtime
        self.config = config or DatabaseConfig()
        self.console = console or Console()

    def start(
        self,
        *,
        pull: bool = False,
        recreate: bool = False,
    ) -> None:
        """Start PostgreSQL database container.

        Args:
            pull: Pull latest image before starting
            recreate: Remove and recreate container if exists

        Process:
            1. Check if container already exists
            2. Pull image if requested
            3. Create data volume if needed
            4. Build container run command
            5. Start container
            6. Wait for health check
            7. Display connection info

        Raises:
            ContainerAlreadyRunningError: If container is already running
            ContainerStartError: If container fails to start
        """

        self.console.rule("[bold blue]Starting PostgreSQL Database Container")

        # Check if already running
        if self.runtime.container_running(self.config.container_name):
            if not recreate:
                raise ContainerAlreadyRunningError(
                    f"Container '{self.config.container_name}' is already running. "
                    "Use --recreate to remove and recreate it."
                )
            self.console.print("[yellow]Removing existing container...[/yellow]")
            self.remove(force=True)

        # Check if exists but stopped
        if self.runtime.container_exists(self.config.container_name):
            if recreate:
                self.console.print("[yellow]Removing existing container...[/yellow]")
                self.remove()
            else:
                self.console.print("[cyan]Starting existing container...[/cyan]")
                self.runtime.run_command(["start", self.config.container_name])
                self.console.print("[green]✓[/green] Container started")
                return

        # Pull image if requested
        if pull:
            self._pull_image()

        # Create volume if needed
        if not self.runtime.volume_exists(self.config.data_volume_name):
            self.console.print(f"[cyan]Creating volume {self.config.data_volume_name}...[/cyan]")
            self.runtime.run_command(["volume", "create", self.config.data_volume_name])

        # Resolve and prepare private key copy
        if self.config.private_key_path and Path(self.config.private_key_path).exists():
            temp_key_path = Path(__file__).parent / "private-key-temp.json"
            try:
                import shutil
                shutil.copy2(self.config.private_key_path, temp_key_path)
                temp_key_path.chmod(0o644)
                self.config.resolved_private_key_path = str(temp_key_path)
                self.console.print(f"[cyan]Prepared private key copy with 644 permissions at {temp_key_path}[/cyan]")
            except Exception as e:  # noqa: BLE001
                self.console.print(f"[yellow]Warning: Failed to prepare private key copy: {e}[/yellow]")

        # Build run command
        run_args = self._build_run_command()

        # Start container
        self.console.print("[cyan]Starting PostgreSQL container...[/cyan]")
        self.runtime.run_command(run_args, check=True)

        # Wait for health
        self._wait_for_health()

        # Align system configurations
        self._align_system_configurations()

        # Display connection info
        self._display_connection_info()

    def _build_run_command(self) -> list[str]:
        """Build docker/podman run command arguments.

        Returns:
            list: Command arguments for container run
        """
        cmd = [
            "run",
            "-d",
            "--name",
            self.config.container_name,
            "--hostname",
            self.config.hostname,
            "-p",
            f"{self.config.host_port}:{self.config.container_port}",
            "-e",
            f"POSTGRES_PASSWORD={self.config.postgres_password}",
            "-e",
            f"POSTGRES_USER={self.config.postgres_user}",
            "-e",
            f"POSTGRES_DB={self.config.postgres_db}",
            "-v",
            f"{self.config.data_volume_name}:/var/lib/postgresql/data",
            "-v",
            "/dev/shm:/dev/shm",  # noqa: S108
            "--shm-size",
            self.config.shm_size,
            "--restart",
            self.config.restart_policy,
            "--log-driver",
            "json-file",
            "--log-opt",
            f"max-size={self.config.log_max_size}",
            "--log-opt",
            f"max-file={self.config.log_max_file}",
            "--health-cmd",
            f"pg_isready -U {self.config.postgres_user} -d {self.config.postgres_db}",
            "--health-interval",
            f"{self.config.health_interval}s",
            "--health-timeout",
            f"{self.config.health_timeout}s",
            "--health-retries",
            str(self.config.health_retries),
        ]
        if getattr(self.config, "resolved_private_key_path", None):
            cmd.extend([
                "-v",
                f"{self.config.resolved_private_key_path}:/etc/postgresql/private-key.json:ro",
            ])
        cmd.append(self.config.image)
        return cmd

    def _pull_image(self) -> None:
        """Pull container image."""
        self.console.print(f"[cyan]Pulling image {self.config.image}...[/cyan]")
        self.runtime.run_command(["pull", self.config.image], check=True)
        self.console.print("[green]✓[/green] Image pulled")

    def _wait_for_health(self) -> None:
        """Wait for container to become healthy."""
        self.console.print("[cyan]Waiting for database to be ready...[/cyan]")

        max_wait = self.config.health_interval * self.config.health_retries
        waited = 0

        while waited < max_wait:
            try:
                status = self.runtime.get_container_status(self.config.container_name)
                if status.get("status") == "running":
                    # Check health
                    _, stdout, _ = self.runtime.run_command(
                        ["inspect", "--format", "{{.State.Health.Status}}", self.config.container_name],
                        check=False,
                    )
                    health_status = stdout.strip()

                    if health_status == "healthy":
                        self.console.print("[green]✓[/green] Database is ready")
                        return
                    if health_status == "unhealthy":
                        raise ContainerStartError("Container became unhealthy")

            except Exception:  # noqa: S110, BLE001
                pass

            time.sleep(2)
            waited += 2

        raise ContainerStartError(f"Database did not become healthy within {max_wait} seconds")

    def _display_connection_info(self) -> None:
        """Display connection information."""
        self.console.print("\n[bold green]✓ Database Started Successfully[/bold green]")
        self.console.print("\n[bold]Connection Details:[/bold]")
        self.console.print("  Host: [cyan]localhost[/cyan]")
        self.console.print(f"  Port: [cyan]{self.config.host_port}[/cyan]")
        self.console.print(f"  Database: [cyan]{self.config.postgres_db}[/cyan]")
        self.console.print(f"  User: [cyan]{self.config.postgres_user}[/cyan]")
        self.console.print(f"  Password: [cyan]{self.config.postgres_password}[/cyan]")
        self.console.print("\n[bold]Connection String:[/bold]")
        self.console.print(
            f"  [cyan]postgresql://{self.config.postgres_user}:{self.config.postgres_password}@localhost:{self.config.host_port}/{self.config.postgres_db}[/cyan]"
        )

    def stop(self) -> None:
        """Stop the database container."""
        from tools.lib.container import ContainerNotFoundError

        self.console.rule("[bold blue]Stopping PostgreSQL Database")

        try:
            if not self.runtime.container_running(self.config.container_name):
                self.console.print("[yellow]Container is not running[/yellow]")
                return

            self.console.print(f"[cyan]Stopping {self.config.container_name}...[/cyan]")
            self.runtime.run_command(["stop", self.config.container_name], check=True)
            self.console.print("[green]✓[/green] Container stopped")

        except ContainerNotFoundError:
            self.console.print("[yellow]Container does not exist[/yellow]")

    def restart(self) -> None:
        """Restart the database container."""
        from tools.lib.container import ContainerNotFoundError

        self.console.rule("[bold blue]Restarting PostgreSQL Database")

        try:
            if not self.runtime.container_exists(self.config.container_name):
                self.console.print("[yellow]Container does not exist. Starting new container...[/yellow]")
                self.start()
                return

            self.console.print(f"[cyan]Restarting {self.config.container_name}...[/cyan]")
            self.runtime.run_command(["restart", self.config.container_name], check=True)
            self.console.print("[green]✓[/green] Container restarted")

        except ContainerNotFoundError:
            self.console.print("[red]Failed to restart container[/red]")
            raise

    def status(self) -> dict[str, str]:
        """Get database container status.

        Returns:
            dict: Container status details
        """
        from tools.lib.container import ContainerNotFoundError

        try:
            return self.runtime.get_container_status(self.config.container_name)
        except ContainerNotFoundError:
            return {"status": "not found", "name": self.config.container_name}

    def logs(self, *, follow: bool = False, tail: int = 50) -> None:
        """Display container logs.

        Args:
            follow: Follow log output
            tail: Number of lines to show from end
        """
        from tools.lib.container import ContainerNotFoundError

        try:
            args = ["logs"]
            if follow:
                args.append("-f")
            args.extend(["--tail", str(tail)])
            args.append(self.config.container_name)

            self.runtime.run_command(args, capture_output=False, check=True)

        except ContainerNotFoundError:
            self.console.print("[red]Container does not exist[/red]")

    def remove(self, *, force: bool = False) -> None:
        """Remove the database container.

        Args:
            force: Force removal even if running
        """
        from tools.lib.container import ContainerNotFoundError

        try:
            if not self.runtime.container_exists(self.config.container_name):
                self.console.print("[yellow]Container does not exist[/yellow]")
                return

            args = ["rm"]
            if force:
                args.append("-f")
            args.append(self.config.container_name)

            self.console.print(f"[cyan]Removing {self.config.container_name}...[/cyan]")
            self.runtime.run_command(args, check=True)
            self.console.print("[green]✓[/green] Container removed")

            # Clean up temporary private key file on host
            temp_key_path = Path(__file__).parent / "private-key-temp.json"
            if temp_key_path.exists():
                try:
                    temp_key_path.unlink()
                    self.console.print("[cyan]Cleaned up temporary private key file[/cyan]")
                except Exception as e:  # noqa: BLE001
                    self.console.print(f"[yellow]Warning: Failed to delete temporary key file: {e}[/yellow]")

        except ContainerNotFoundError:
            self.console.print("[yellow]Container does not exist[/yellow]")

    def exec_sql(self, sql: str, *, user: str | None = None, check: bool = True) -> str:
        """Execute a SQL statement inside the database container."""
        conn_user = user or self.config.postgres_user
        args = [
            "exec",
            "-i",
            self.config.container_name,
            "psql",
            "-U",
            conn_user,
            "-d",
            self.config.postgres_db,
            "-t",  # Tuple only / quiet mode
            "-c",
            sql,
        ]
        _, stdout, stderr = self.runtime.run_command(args, check=check)
        if stderr.strip():
            self.console.print(f"[yellow]SQL Warning: {stderr.strip()}[/yellow]")
        return stdout.strip()

    def _align_system_configurations(self) -> None:
        """Align AlloyDB Omni features including extensions and Columnar Engine."""
        self.console.print("[cyan]Aligning AlloyDB Omni features...[/cyan]")

        # 1. Enable extensions as superuser alloydbadmin
        self.exec_sql("CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;", user="alloydbadmin")
        self.exec_sql("CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;", user="alloydbadmin")

        # 2. Check Columnar Engine
        columnar_status = self.exec_sql("SHOW google_columnar_engine.enabled;", user="alloydbadmin")

        needs_restart = False
        if columnar_status.strip() != "on":
            self.console.print("[yellow]Enabling AlloyDB Columnar Engine...[/yellow]")
            self.exec_sql("ALTER SYSTEM SET google_columnar_engine.enabled = 'on';", user="alloydbadmin")
            self.exec_sql("ALTER SYSTEM SET google_columnar_engine.memory_size_in_mb = 2048;", user="alloydbadmin")
            needs_restart = True

        # 3. Check ML Agent Process (if credentials provided)
        if self.config.private_key_path:
            # We don't need to change key owner or permissions here because we prepare a 644 readable key copy on the host before mount.
            ml_agent_status = self.exec_sql("SHOW omni_enable_ml_agent_process;", user="alloydbadmin")
            if ml_agent_status.strip() != "on":
                self.console.print("[yellow]Enabling ML agent process...[/yellow]")
                self.exec_sql("ALTER SYSTEM SET omni_enable_ml_agent_process = 'on';", user="alloydbadmin")
                self.exec_sql("ALTER SYSTEM SET omni_google_cloud_private_key_file_path = '/etc/postgresql/private-key.json';", user="alloydbadmin")
                needs_restart = True

        if needs_restart:
            self.console.print("[yellow]Restarting container to apply system parameters...[/yellow]")
            # Call docker/podman restart directly to preserve volume state
            self.runtime.run_command(["restart", self.config.container_name])
            time.sleep(5)
            self._wait_for_health()
            # Re-execute extensions install verification
            self.exec_sql("CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;", user="alloydbadmin")
            self.exec_sql("CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;", user="alloydbadmin")

        # 4. Register gemini-embedding-2 model endpoint if needed
        model_exists = self.exec_sql("SELECT EXISTS (SELECT 1 FROM google_ml.models WHERE id = 'gemini-embedding-2');", user="alloydbadmin")
        if model_exists.strip() != "t":
            self.console.print("[yellow]Registering gemini-embedding-2 model endpoint...[/yellow]")
            self.exec_sql(
                "CALL google_ml.create_model("
                "  model_id => 'gemini-embedding-2',"
                "  model_provider => 'google',"
                "  model_type => 'text_embedding',"
                "  model_qualified_name => 'gemini-embedding-2',"
                "  model_auth_type => 'alloydb_service_agent_iam'"
                ");",
                user="alloydbadmin"
            )


class DatabaseError(Exception):
    """Base exception for database errors."""


class ContainerAlreadyRunningError(DatabaseError):
    """Raised when container is already running."""


class ContainerStartError(DatabaseError):
    """Raised when container fails to start."""
