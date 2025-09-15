"""Application core plugin."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol

if TYPE_CHECKING:
    from click import Group
    from litestar.config.app import AppConfig


class ApplicationCore(InitPluginProtocol, CLIPluginProtocol):
    """Application core configuration plugin.

    This class is responsible for configuring the main Litestar application
    with routes, dependencies, and various plugins following SQLStack patterns.
    """

    __slots__ = ("app_name",)
    app_name: str

    def on_cli_init(self, cli: Group) -> None:
        """Configure CLI commands."""
        from app.lib.settings import get_settings

        settings = get_settings()
        self.app_name = settings.app.NAME

        # Commands are automatically added by importing the commands module
        # which extends SQLSpec's database group
        from app.cli import commands  # noqa: F401

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application for use with SQLSpec and our services.

        Args:
            app_config: The AppConfig instance.

        Returns:
            The configured app config.
        """

        from litestar.contrib.jinja import JinjaTemplateEngine
        from litestar.enums import RequestEncodingType
        from litestar.openapi import OpenAPIConfig
        from litestar.openapi.plugins import ScalarRenderPlugin
        from litestar.params import Body
        from litestar.plugins.htmx import HTMXRequest
        from litestar.static_files import create_static_files_router
        from litestar.template.config import TemplateConfig
        from sqlspec import ConnectionT, PoolT

        from app import config
        from app import schemas as s
        from app.lib.log import StructlogMiddleware, after_exception_hook_handler
        from app.lib.settings import get_settings
        from app.server import plugins
        from app.server.controllers import CoffeeChatController
        from app.server.exceptions import exception_handlers
        from app.utils.serialization import (
            general_dec_hook,
            numpy_array_enc_hook,
            numpy_array_predicate,
        )

        settings = get_settings()
        self.app_name = settings.app.NAME
        app_config.debug = settings.app.DEBUG

        # Set HTMXRequest as the default request class
        app_config.request_class = HTMXRequest

        # Logging middleware
        app_config.middleware.insert(0, StructlogMiddleware)
        app_config.after_exception.append(after_exception_hook_handler)

        # OpenAPI configuration
        app_config.openapi_config = OpenAPIConfig(
            title=settings.app.NAME,
            version="0.1.0",
            use_handler_docstrings=True,
            render_plugins=[ScalarRenderPlugin(version="latest")],
        )
        app_config.cors_config = config.cors
        app_config.plugins.extend(
            [
                plugins.structlog,
                plugins.granian,
                plugins.sqlspec,
                plugins.problem_details,
                plugins.htmx,
            ],
        )

        app_config.template_config = TemplateConfig(
            directory=settings.app.TEMPLATE_DIR,
            engine=JinjaTemplateEngine,
        )
        app_config.exception_handlers.update(exception_handlers)  # type: ignore[arg-type]

        app_config.route_handlers.extend([
            CoffeeChatController,
            create_static_files_router(
                path="/static",
                directories=[settings.app.STATIC_DIR],
                name="static",
            ),
        ])

        # Signature namespace for dependency injection
        from app.agents.orchestrator import ADKOrchestrator
        from app.services.cache import CacheService
        from app.services.chat import ChatService
        from app.services.embedding import EmbeddingService
        from app.services.metrics import MetricsService
        from app.services.product import ProductService
        from app.services.vertex_ai import VertexAIService

        app_config.signature_namespace.update({
            "RequestEncodingType": RequestEncodingType,
            "Body": Body,
            "s": s,
            "ADKOrchestrator": ADKOrchestrator,
            "CacheService": CacheService,
            "ChatService": ChatService,
            "EmbeddingService": EmbeddingService,
            "MetricsService": MetricsService,
            "ProductService": ProductService,
            "VertexAIService": VertexAIService,
            "ConnectionT": ConnectionT,
            "PoolT": PoolT,
            "UUID": UUID,
            "datetime": datetime,
        })

        app_config.type_encoders = {np.ndarray: numpy_array_enc_hook}
        app_config.type_decoders = [(numpy_array_predicate, general_dec_hook)]
        return app_config
