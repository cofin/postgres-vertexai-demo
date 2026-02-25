"""Inversion of Control container setup.

Centralizes all DI provider registration and container creation.
Follows the DMA accelerator pattern for clean separation of concerns.
"""

from dishka import AsyncContainer, Provider, make_async_container

from cymbal.server.providers import ADKProvider, CoreServiceProvider, SQLSpecProvider


def create_container() -> AsyncContainer:
    """Create the main DI container with all providers.

    Returns:
        Configured AsyncContainer with all application providers.
    """
    return make_async_container(SQLSpecProvider(), CoreServiceProvider(), ADKProvider())


def create_container_with_providers(*additional_providers: Provider) -> AsyncContainer:
    """Create container with additional custom providers.

    Args:
        *additional_providers: Additional Provider instances to include.

    Returns:
        Configured AsyncContainer with base + additional providers.
    """
    base_providers = [SQLSpecProvider(), CoreServiceProvider(), ADKProvider()]
    return make_async_container(*base_providers, *additional_providers)


def create_litestar_container() -> AsyncContainer:
    """Create container optimized for Litestar web runtime.

    Returns:
        AsyncContainer configured for web request handling.
    """
    return create_container()


def create_cli_container() -> AsyncContainer:
    """Create container optimized for CLI/runtime usage.

    Returns:
        AsyncContainer configured for background jobs and CLI commands.
    """
    return create_container()
