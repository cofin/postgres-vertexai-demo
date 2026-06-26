# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from collections.abc import AsyncIterator

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import AsyncTestClient

from app.lib import settings as app_settings

if TYPE_CHECKING:
    from pytest import MonkeyPatch


pytestmark = pytest.mark.anyio

# Tests connect to the repo-managed PostgreSQL/AlloyDB Omni database. Start it with
# `make start-infra` and apply migrations with
# `uv run python manage.py database upgrade --no-prompt`; pytest owns per-test state only.


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: MonkeyPatch) -> None:
    """Patch the settings with test configuration.

    Loads the test settings from the project-root .env.testing.
    """
    settings = app_settings.Settings.from_env(".env.testing")

    def get_settings(dotenv_filename: str = ".env.testing") -> app_settings.Settings:
        return settings

    monkeypatch.setattr(app_settings, "get_settings", get_settings)


@pytest.fixture
def app() -> Litestar:
    """Create test app instance."""
    from app.server.asgi import create_app

    return create_app()


@pytest.fixture
async def client(app: Litestar) -> AsyncIterator[AsyncTestClient]:
    """Create test client.

    Enters the AsyncTestClient as a context manager so the Litestar lifespan
    runs — this is what closes the Dishka container and Oracle pool between
    tests. Without it, container.close() is never invoked and subsequent
    tests fail with 500 errors from leaked pool handles.

    Yields:
        AsyncTestClient bound to ``app`` with the lifespan entered.
    """
    from litestar.testing import AsyncTestClient

    async with AsyncTestClient(app=app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
async def htmx_client(app: Litestar) -> AsyncIterator[AsyncTestClient]:
    """Test client that masquerades as HTMX (sends ``HX-Request: true``).

    Yields:
        AsyncTestClient that always sends ``HX-Request: true``.
    """
    from litestar.testing import AsyncTestClient

    async with AsyncTestClient(app=app, raise_server_exceptions=False) as test_client:
        test_client.headers["HX-Request"] = "true"
        yield test_client


@pytest.fixture(autouse=True)
async def _cleanup_db_pool() -> AsyncIterator[None]:
    """Ensure database connection pool is closed and configuration is reset after each test."""
    yield
    from app.config import _reset, db_manager
    try:
        # Check if SQLSpec database manager has an active driver and close it.
        if hasattr(db_manager, "driver") and db_manager.driver is not None:
            # Check if the connection pool is open and close it.
            # SQLSpec Asyncpg uses `connection_instance` to represent the driver pool connection
            if hasattr(db_manager.driver, "connection_instance") and db_manager.driver.connection_instance is not None:
                await db_manager.driver.close()
    except Exception as e:  # noqa: BLE001
        print(f"Warning: failed to close database driver during test cleanup: {e}")
    finally:
        # Discard cached configuration so next test re-initializes a fresh pool on the current loop
        _reset()
