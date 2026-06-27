# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
    # Ensure we have a dummy API key for testing if Vertex AI is not configured
    if not settings.vertex_ai.PROJECT_ID and not settings.vertex_ai.API_KEY:
        settings.vertex_ai.API_KEY = "dummy-api-key-for-testing"

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
