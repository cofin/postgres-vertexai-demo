from __future__ import annotations

import pytest
from litestar.contrib.jinja import JinjaTemplateEngine


@pytest.fixture(scope="session", autouse=True)
def _set_database_url() -> None:
    """Ensure DATABASE_URL is parseable when .env uses template variables."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test_app:test-secret@localhost:1521/test_app",
    )
    yield
    monkeypatch.undo()


def test_vite_template_callables_registered(app) -> None:
    template_engine = app.template_engine
    assert isinstance(template_engine, JinjaTemplateEngine)

    globals_map = template_engine.engine.globals
    assert "vite" in globals_map
    assert "vite_hmr" in globals_map
    assert "vite_routes" in globals_map
    assert "vite_static" in globals_map
