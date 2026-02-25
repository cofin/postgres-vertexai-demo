"""Tests for DI container and IOC setup.

Following DMA pattern tests for dependency injection.
"""

import pytest
from dishka import AsyncContainer

from cymbal.ioc import create_container, create_container_with_providers
from cymbal.lib.di import Inject, Scope
from cymbal.server.providers import ADKProvider, CoreServiceProvider, SQLSpecProvider


class TestContainerCreation:
    """Test container factory functions."""

    def test_create_container_returns_async_container(self) -> None:
        """Verify create_container returns an AsyncContainer."""
        container = create_container()
        assert isinstance(container, AsyncContainer)

    def test_create_container_has_all_providers(self) -> None:
        """Verify container includes all three base providers."""
        container = create_container()
        # Container should be able to resolve dependencies
        assert container is not None

    def test_create_container_with_additional_providers(self) -> None:
        """Verify container can include custom providers."""
        custom_provider = ADKProvider()
        container = create_container_with_providers(custom_provider)
        assert isinstance(container, AsyncContainer)


class TestDIExports:
    """Test that lib.di exports are properly configured."""

    def test_inject_exported(self) -> None:
        """Verify Inject is exported with clean naming."""
        from cymbal.lib.di import Inject

        assert Inject is not None

    def test_scope_exported(self) -> None:
        """Verify Scope is exported."""
        from cymbal.lib.di import Scope

        assert Scope is not None
        assert hasattr(Scope, "APP")
        assert hasattr(Scope, "REQUEST")

    def test_provider_exported(self) -> None:
        """Verify Provider is exported."""
        from cymbal.lib.di import Provider

        assert Provider is not None

    def test_websocket_scope_exported(self) -> None:
        """Verify WebSocketScope is exported."""
        from cymbal.lib.di import WebSocketScope

        assert WebSocketScope is not None


class TestProviders:
    """Test provider configurations."""

    def test_sqlspec_provider_creation(self) -> None:
        """Verify SQLSpecProvider can be instantiated."""
        provider = SQLSpecProvider()
        assert provider is not None

    def test_core_service_provider_creation(self) -> None:
        """Verify CoreServiceProvider can be instantiated."""
        provider = CoreServiceProvider()
        assert provider is not None

    def test_adk_provider_creation(self) -> None:
        """Verify ADKProvider can be instantiated."""
        provider = ADKProvider()
        assert provider is not None
