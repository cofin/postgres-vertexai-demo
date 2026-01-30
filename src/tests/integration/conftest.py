from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.testing import AsyncTestClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from litestar import Litestar


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Create test client."""
    async with AsyncTestClient(app=app) as c:
        yield c


@pytest.fixture
def app() -> Litestar:
    """Create test app instance."""
    from app.server.asgi import create_app

    return create_app()
