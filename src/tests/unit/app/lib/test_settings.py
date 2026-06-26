# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Database settings contracts for SQLSpec Oracle integrations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_litestar_env_defaults_app_url_from_litestar_port(monkeypatch: MonkeyPatch) -> None:
    from app.lib.settings import Settings

    monkeypatch.delenv("APP_URL", raising=False)
    monkeypatch.setenv("LITESTAR_PORT", "5006")

    Settings().setup_litestar_env()

    assert os.environ["APP_URL"] == "http://localhost:5006"


def test_litestar_env_preserves_explicit_app_url(monkeypatch: MonkeyPatch) -> None:
    from app.lib.settings import Settings

    monkeypatch.setenv("APP_URL", "https://coffee.example.test")

    Settings().setup_litestar_env()

    assert os.environ["APP_URL"] == "https://coffee.example.test"


def test_vite_config_uses_resources_as_frontend_root() -> None:
    from app.lib.settings import BASE_DIR, ViteSettings

    config = ViteSettings().get_config()

    assert config.paths.root == BASE_DIR.parent / "resources"
    assert config.paths.resource_dir == Path()
    assert config.paths.static_dir == Path("public")
    assert config.types is not None
    assert config.types.output == BASE_DIR.parent / "resources" / "generated"
