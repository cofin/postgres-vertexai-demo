"""Cymbal database and server configurations.

This module serves as a thin facade that materializes configuration objects
from settings classes. Following the litestar-fullstack-spa pattern, all
configuration logic lives in settings.py via get_config() methods.
"""

import logging
import warnings

import structlog
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.stores.registry import StoreRegistry
from litestar.template.config import TemplateConfig
from sqlspec import SQLSpec
from sqlspec.adapters.asyncpg.litestar import AsyncpgStore
from sqlspec.observability import ObservabilityConfig

from cymbal.lib import log as log_conf
from cymbal.lib.settings import BASE_DIR, get_settings

_settings = get_settings()
settings = _settings  # Alias for compatibility

# Observability (SQL logging)
_observability = ObservabilityConfig(print_sql=_settings.db.ECHO)
db_manager = SQLSpec(observability_config=_observability)
db = db_manager.add_config(_settings.db.get_config())
# Load SQL files - we will create this directory in Ch3
db_manager.load_sql_files(BASE_DIR / "db" / "sql")

stores = StoreRegistry(stores={"sessions": AsyncpgStore(config=db)})  # type: ignore[dict-item]
session = ServerSideSessionConfig(store="sessions")
templates = TemplateConfig(
    directory=BASE_DIR / "server" / "templates",
    engine=JinjaTemplateEngine,
)
compression = _settings.app.get_compression_config()
csrf = _settings.app.get_csrf_config()
cors = _settings.app.get_cors_config()
problem_details = _settings.app.get_problem_details_config()
vite = _settings.vite.get_config()
channels = _settings.channels.get_config()
log = _settings.logging.get_structlog_config()
email = _settings.email.get_email_config()


def setup_logging() -> None:
    """Set up structured logging configuration.

    Configures both structlog and standard library logging for the application.
    """
    if log.structlog_logging_config.standard_lib_logging_config:
        log.structlog_logging_config.standard_lib_logging_config.configure()
    log.structlog_logging_config.configure()
    structlog.configure(
        cache_logger_on_first_use=True,
        logger_factory=log.structlog_logging_config.logger_factory,
        processors=log.structlog_logging_config.processors,
        wrapper_class=structlog.make_filtering_bound_logger(_settings.logging.LEVEL),
    )
    # Capture Python warnings into logging so we can filter them
    logging.captureWarnings(True)

    # Add filter to suppress specific ADK/GenAI warnings
    adk_warning_filter = log_conf.SuppressADKWarningsFilter()

    # Apply to py.warnings logger (where Python warnings get captured)
    py_warnings_logger = logging.getLogger("py.warnings")
    py_warnings_logger.addFilter(adk_warning_filter)

    # Apply to specific Google loggers
    for logger_name in ["google.adk", "google.genai", "google_genai", "google_genai.types"]:
        logger = logging.getLogger(logger_name)
        logger.addFilter(adk_warning_filter)

    # Also apply to root logger and queue_listener handlers to catch in listener thread
    logging.root.addFilter(adk_warning_filter)

    # Suppress asyncio "Task exception was never retrieved" messages
    asyncio_filter = log_conf.SuppressAsyncioTaskExceptionFilter()
    logging.getLogger("asyncio").addFilter(asyncio_filter)

    # Suppress duplicate traceback when message already contains a formatted traceback
    granian_exc_filter = log_conf.SuppressGranianExcInfoFilter()
    logging.getLogger("_granian").addFilter(granian_exc_filter)

    # Suppress at Python warnings level too (belt and suspenders)
    warnings.filterwarnings(
        "ignore",
        message=r".*non-text parts in the response.*function_call.*",
        category=Warning,
        module=r"google_(?:genai|generativeai)(?:\..*)?$",
    )
