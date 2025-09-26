"""Application configuration management."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import structlog
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.exceptions import (
    NotAuthorizedException,
    PermissionDeniedException,
)
from litestar.logging.config import (
    LoggingConfig,
    StructLoggingConfig,
    default_logger_factory,
)
from litestar.middleware.logging import LoggingMiddlewareConfig
from litestar.plugins.problem_details import ProblemDetailsConfig
from litestar.plugins.structlog import StructlogConfig
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.extensions.litestar import DatabaseConfig, SQLSpec

from app.lib import log as log_conf
from app.lib.settings import get_settings
from app.services.locator import ServiceLocator

settings = get_settings()


compression = CompressionConfig(backend="gzip")
csrf = CSRFConfig(
    secret=settings.app.SECRET_KEY,
    cookie_secure=settings.app.CSRF_COOKIE_SECURE,
    cookie_name=settings.app.CSRF_COOKIE_NAME,
    header_name=settings.app.CSRF_HEADER_NAME,
)
cors = CORSConfig(allow_origins=cast("list[str]", settings.app.ALLOWED_CORS_ORIGINS))
problem_details = ProblemDetailsConfig(enable_for_all_http_exceptions=True)
db = AsyncpgConfig(
    pool_config={
        "dsn": settings.db.URL,
        "min_size": settings.db.POOL_MIN_SIZE,
        "max_size": settings.db.POOL_MAX_SIZE,
        "timeout": settings.db.POOL_TIMEOUT,
        "command_timeout": settings.db.POOL_RECYCLE,
    },
    migration_config={
        "version_table_name": "migrations",
        "script_location": settings.db.MIGRATION_PATH,
        "project_root": Path(__file__).parent.parent,
    },
)

# SQLSpec database manager
sqlspec = SQLSpec(config=DatabaseConfig(commit_mode="autocommit", config=db))

# Load SQL files
sqlspec.load_sql_files(Path(__file__).parent / "db" / "sql")

# Global service locator
service_locator = ServiceLocator()


log = StructlogConfig(
    enable_middleware_logging=False,
    structlog_logging_config=StructLoggingConfig(
        log_exceptions="always",
        processors=log_conf.structlog_processors(as_json=not log_conf.is_tty()),  # type: ignore[has-type,unused-ignore]
        logger_factory=default_logger_factory(as_json=not log_conf.is_tty()),  # type: ignore[has-type,unused-ignore]
        disable_stack_trace={404, 401, 403, NotAuthorizedException, PermissionDeniedException},
        standard_lib_logging_config=LoggingConfig(
            log_exceptions="always",
            disable_stack_trace={404, 401, 403, NotAuthorizedException, PermissionDeniedException},
            root={"level": logging.getLevelName(settings.log.LEVEL), "handlers": ["queue_listener"]},
            formatters={
                "standard": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": log_conf.stdlib_logger_processors(as_json=not log_conf.is_tty()),  # type: ignore[has-type,unused-ignore]
                },
            },
            loggers={
                "sqlspec": {
                    "propagate": False,
                    "level": settings.log.SQLSPEC_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "sqlglot": {
                    "propagate": False,
                    "level": settings.log.SQLGLOT_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "_granian": {
                    "propagate": False,
                    "level": settings.log.ASGI_ERROR_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "granian.server": {
                    "propagate": False,
                    "level": settings.log.ASGI_ERROR_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "granian.access": {
                    "propagate": False,
                    "level": settings.log.ASGI_ACCESS_LEVEL,
                    "handlers": ["queue_listener"],
                },
            },
        ),
    ),
    middleware_logging_config=LoggingMiddlewareConfig(
        request_log_fields=settings.log.REQUEST_FIELDS,
        response_log_fields=settings.log.RESPONSE_FIELDS,
    ),
)


def setup_logging() -> None:
    """Return a configured logger for the given name.

    Args:
        args: positional arguments to pass to the bound logger instance
        kwargs: keyword arguments to pass to the bound logger instance

    """
    if log.structlog_logging_config.standard_lib_logging_config:
        log.structlog_logging_config.standard_lib_logging_config.configure()
    log.structlog_logging_config.configure()
    structlog.configure(
        cache_logger_on_first_use=True,
        logger_factory=log.structlog_logging_config.logger_factory,
        processors=log.structlog_logging_config.processors,
        wrapper_class=structlog.make_filtering_bound_logger(settings.log.LEVEL),
    )
