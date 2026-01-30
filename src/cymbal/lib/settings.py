"""Configuration management for Cymbal via environment variables."""

import logging
import os
import tempfile
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, cast
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlspec.adapters.asyncpg import AsyncpgConfig
from litestar.utils.module_loader import module_to_os_path

from cymbal.lib.exceptions import ConfigurationError
from cymbal.utils.env import get_config_val, get_env

if TYPE_CHECKING:
    from litestar.channels import ChannelsPlugin
    from litestar.config.compression import CompressionConfig
    from litestar.config.cors import CORSConfig
    from litestar.config.csrf import CSRFConfig
    from litestar.plugins.problem_details import ProblemDetailsConfig
    from litestar.plugins.structlog import StructlogConfig
    from litestar_email import EmailConfig
    from litestar_vite import ViteConfig


DEFAULT_MODULE_NAME = "cymbal"
BASE_DIR: Final[Path] = module_to_os_path(DEFAULT_MODULE_NAME)
STATIC_DIR = Path(BASE_DIR / "server" / "static")
CONFIG_DIR = Path.home() / ".cymbal"
# Placeholder paths for future expansion
COLLECTOR_TEMPLATES_DIR = BASE_DIR / "collector" / "templates"
SQL_SOURCES_DIR = BASE_DIR / "collector" / "sql" / "sources"
TRANSFORMER_SQL_DIR = BASE_DIR / "transformer" / "sql"
TRANSFORMER_DMA_CLASSIC_SQL_DIR = BASE_DIR / "transformer" / "formats" / "dma_classic" / "sql"

TRUE_VALUES = {"True", "true", "1", "yes", "Y", "T"}

@dataclass
class DatabaseSettings:
    """Database connection settings following SQLSpec patterns."""

    URL: str | None = field(default_factory=get_env("DATABASE_URL", None))
    """Database URL. If None, constructed from components."""

    USER: str = field(default_factory=get_env("DATABASE_USER", "app"))
    """PostgreSQL Database User."""
    PASSWORD: str = field(default_factory=get_env("DATABASE_PASSWORD", "super-secret"))
    """PostgreSQL Database Password."""
    HOST: str = field(default_factory=get_env("DATABASE_HOST", "localhost"))
    """PostgreSQL Database Host."""
    PORT: int = field(default_factory=get_env("DATABASE_PORT", 5432))
    """PostgreSQL Database Port."""
    DATABASE: str = field(default_factory=get_env("DATABASE_NAME", "app"))
    """PostgreSQL Database Name."""

    # Main Pool Settings
    POOL_MIN_SIZE: int = field(default_factory=get_env("DATABASE_POOL_MIN_SIZE", 5))
    """Min size for AsyncPG connection pool."""
    POOL_MAX_SIZE: int = field(default_factory=get_env("DATABASE_POOL_MAX_SIZE", 20))
    """Max size for AsyncPG connection pool."""
    POOL_TIMEOUT: int = field(default_factory=get_env("DATABASE_POOL_TIMEOUT", 30))
    """Time in seconds for connection timeout."""

    POOL_RECYCLE: int = field(default_factory=get_env("DATABASE_POOL_RECYCLE", 300))
    """Command timeout in seconds."""
    ECHO: bool = field(default_factory=get_env("DATABASE_ECHO", False))
    """Print SQL statements to console for debugging."""
    MIGRATION_PATH: str = field(
        default_factory=get_env("DATABASE_MIGRATION_PATH", str(BASE_DIR / "db" / "migrations"))
    )
    """The path to database migrations."""
    MIGRATION_DDL_VERSION_TABLE: str = field(
        default_factory=get_env("DATABASE_MIGRATION_DDL_VERSION_TABLE", "migrations")
    )
    """The name to use for the migrations versions table name."""
    FIXTURE_PATH: str = field(default_factory=get_env("DATABASE_FIXTURE_PATH", str(BASE_DIR / "db" / "fixtures")))
    """The path to JSON fixture files to load into tables."""

    def get_connection_params(self) -> dict[str, Any]:
        """Extract connection parameters for PostgreSQL."""
        if self.URL:
            parsed = urlparse(self.URL)
            return {
                "user": parsed.username or self.USER,
                "password": parsed.password or self.PASSWORD,
                "host": parsed.hostname or self.HOST,
                "port": parsed.port or self.PORT,
                "database": parsed.path.lstrip("/") if parsed.path else self.DATABASE,
            }
        return {
            "user": self.USER,
            "password": self.PASSWORD,
            "host": self.HOST,
            "port": self.PORT,
            "database": self.DATABASE,
        }

    def get_database_url(self) -> str:
        """Get the database URL for connection strings."""
        if self.URL:
            return self.URL
        params = self.get_connection_params()
        return (
            f"postgresql://{params['user']}:{params['password']}@{params['host']}:{params['port']}/{params['database']}"
        )

    def get_config(self) -> AsyncpgConfig:
        """Create PostgreSQL database configuration for main application."""
        conn_params = self.get_connection_params()

        connection_config = {
            "user": conn_params["user"],
            "password": conn_params["password"],
            "host": conn_params["host"],
            "port": conn_params["port"],
            "database": conn_params["database"],
            "min_size": self.POOL_MIN_SIZE,
            "max_size": self.POOL_MAX_SIZE,
            "timeout": self.POOL_TIMEOUT,
            "command_timeout": 60,
            "max_queries": 50000,
            "max_inactive_connection_lifetime": float(self.POOL_RECYCLE),
        }

        return AsyncpgConfig(
            connection_config=connection_config, # sqlspec > 0.14 uses connection_config not pool_config
            migration_config={
                "version_table_name": self.MIGRATION_DDL_VERSION_TABLE,
                "script_location": self.MIGRATION_PATH,
                "project_root": BASE_DIR,
                "include_extensions": ["litestar"],
            },
            extension_config={
                "litestar": {"session_table": "app_session", "disable_di": True}
            },
        )


@dataclass
class ETLSettings:
    """Database connection settings following SQLSpec patterns."""
    # Placeholder for future use
    WORKING_PATH: str | None = field(default_factory=get_env("ETL_WORKING_PATH", None))

    def get_working_path(self) -> Path:
        working_path = Path(self.WORKING_PATH) if self.WORKING_PATH else Path(tempfile.gettempdir())
        working_path.mkdir(parents=True, exist_ok=True)
        return working_path


@dataclass
class CollectorSettings:
    """Database collector configuration."""
    # Placeholder
    DEFAULT_OUTPUT_DIR: Path = field(default_factory=get_env("OUTPUT_DIR", Path("./dist")))


def _get_sqlspec_log_level() -> int:
    explicit_level = os.getenv("SQLSPEC_LOG_LEVEL")
    if explicit_level:
        return int(explicit_level)
    return 20  # INFO by default


@dataclass
class LoggingSettings:
    """Logging configuration following SQLSpec patterns."""

    LEVEL: int = field(default_factory=get_env("LOG_LEVEL", 20))

    SQLSPEC_LEVEL: int = field(default_factory=_get_sqlspec_log_level)
    SQLGLOT_LEVEL: int = field(default_factory=get_env("SQLGLOT_LOG_LEVEL", 40))

    ASGI_ERROR_LEVEL: int = field(default_factory=get_env("ASGI_ERROR_LOG_LEVEL", 40))
    ASGI_ACCESS_LEVEL: int = field(default_factory=get_env("ASGI_ACCESS_LOG_LEVEL", 30))

    REQUEST_FIELDS: set[str] = field(
        default_factory=lambda: set(get_env("LOG_REQUEST_FIELDS", ["method", "path", "query"])())
    )
    RESPONSE_FIELDS: set[str] = field(
        default_factory=lambda: set(get_env("LOG_RESPONSE_FIELDS", ["status_code"])())
    )

    EXCLUDE_PATHS: str = field(
        default_factory=get_env(
            "LOG_EXCLUDE_PATHS",
            r"^/health|^/static/|^/assets/|^/favicons/|^/@vite|^/@fs|^/node_modules|\.(?:js|css|ico|png|jpg|svg|woff2?)$",
        )
    )
    INCLUDE_COMPRESSED_BODY: bool = field(default_factory=get_env("LOG_INCLUDE_COMPRESSED_BODY", False))
    OBFUSCATE_COOKIES: set[str] = field(
        default_factory=lambda: set(
            get_env("LOG_OBFUSCATE_COOKIES", ["session", "csrf", "XSRF-TOKEN", "refresh_token"])()
        )
    )
    OBFUSCATE_HEADERS: set[str] = field(
        default_factory=lambda: set(get_env("LOG_OBFUSCATE_HEADERS", ["authorization", "x-api-key"])())
    )

    def get_structlog_config(self) -> "StructlogConfig":
        from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
        from litestar.logging.config import LoggingConfig, StructLoggingConfig, default_logger_factory
        from litestar.middleware.logging import LoggingMiddlewareConfig
        from litestar.plugins.structlog import StructlogConfig

        from cymbal.lib import log as log_conf
        from cymbal.lib.exceptions import (
            ClientError,
            ConflictError,
            NotFoundError,
            PasswordValidationError,
            ValidationError,
        )

        return StructlogConfig(
            enable_middleware_logging=False,
            structlog_logging_config=StructLoggingConfig(
                log_exceptions="always",
                processors=log_conf.structlog_processors(as_json=not log_conf.is_tty()),  # type: ignore[has-type,unused-ignore]
                logger_factory=default_logger_factory(as_json=not log_conf.is_tty()),  # type: ignore[has-type,unused-ignore]
                disable_stack_trace={
                    400, 401, 403, 404, 409,
                    ClientError, ConflictError, NotAuthorizedException, NotFoundError,
                    PasswordValidationError, PermissionDeniedException, ValidationError,
                },
                standard_lib_logging_config=LoggingConfig(
                    log_exceptions="always",
                    disable_stack_trace={
                        400, 401, 403, 404, 409,
                        ClientError, ConflictError, NotAuthorizedException, NotFoundError,
                        PasswordValidationError, PermissionDeniedException, ValidationError,
                    },
                    root={"level": logging.getLevelName(self.LEVEL), "handlers": ["queue_listener"]},
                    formatters={
                        "standard": {
                            "()": "structlog.stdlib.ProcessorFormatter",
                            "processors": log_conf.stdlib_logger_processors(as_json=not log_conf.is_tty()),  # type: ignore[has-type,unused-ignore]
                        }
                    },
                    loggers={
                        "sqlspec.driver": {
                            "propagate": False,
                            "level": self.SQLSPEC_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "sqlglot": {"propagate": False, "level": self.SQLGLOT_LEVEL, "handlers": ["queue_listener"]},
                        "_granian": {
                            "propagate": False,
                            "level": self.ASGI_ERROR_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "granian.server": {
                            "propagate": False,
                            "level": self.ASGI_ERROR_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "granian.access": {
                            "propagate": False,
                            "level": self.ASGI_ACCESS_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "google.adk": {
                            "propagate": False,
                            "level": self.LEVEL,
                            "handlers": ["queue_listener"],
                        },
                    },
                ),
            ),
            middleware_logging_config=LoggingMiddlewareConfig(
                request_log_fields=self.REQUEST_FIELDS,  # type: ignore[arg-type]
                response_log_fields=self.RESPONSE_FIELDS,  # type: ignore[arg-type]
            ),
        )


@dataclass
class EmailSettings:
    """Email configuration settings."""
    BACKEND: str = field(default_factory=get_env("EMAIL_BACKEND", "console"))
    # Stub implementation for now
    def get_email_config(self) -> Any:
        return None


@dataclass
class TaskSettings:
    """Task execution settings."""
    DEFAULT_EXECUTION_TARGET: Literal["local", "cloudrun", "immediate"] = cast(
        'Literal["local", "cloudrun", "immediate"]', field(default_factory=get_env("EXECUTION_TARGET", "local"))
    )
    INPROCESS_WORKER: bool = field(default_factory=get_env("INPROCESS_WORKER", True))


@dataclass
class GoogleCloudSettings:
    """Google Cloud Platform integration settings."""
    PROJECT_ID: str | None = field(default_factory=get_env("GOOGLE_CLOUD_PROJECT", None))
    CREDENTIALS_PATH: str | None = field(default_factory=get_env("GOOGLE_APPLICATION_CREDENTIALS", None))
    REGION: str = field(default_factory=get_env("GCP_REGION", "us-central1"))


@dataclass
class AppSettings:
    """Application-wide settings."""

    NAME: str = field(default="Cymbal Coffee")
    VERSION: str = field(default="0.3.0")
    BUILD_NUMBER: str | None = field(default_factory=get_env("BUILD_NUMBER", None))
    SLUG: str = field(default="cymbal")

    APP_URL: str = field(default_factory=get_env("APP_URL", "http://localhost:8000"))
    """Base URL for the application."""

    CONFIG_DIR: Path = field(default_factory=get_env("CONFIG_DIR", CONFIG_DIR))

    DEBUG: bool = field(default_factory=get_env("LITESTAR_DEBUG", False))
    DEV_MODE: bool = field(default_factory=get_env("DEV_MODE", False))

    SECRET_KEY: str = field(default_factory=get_env("SECRET_KEY", "super-secret-key-change-in-production"))
    """Secret key for session management and CSRF protection."""
    COOKIE_SECURE: bool = field(default_factory=get_env("COOKIE_SECURE", True))
    
    CSRF_COOKIE_SECURE: bool = field(default_factory=get_env("CSRF_COOKIE_SECURE", True))
    CSRF_COOKIE_NAME: str = field(default_factory=get_env("CSRF_COOKIE_NAME", "XSRF-TOKEN"))
    CSRF_HEADER_NAME: str = field(default_factory=get_env("CSRF_HEADER_NAME", "X-XSRF-TOKEN"))

    ALLOWED_CORS_ORIGINS: list[str] = field(
        default_factory=get_env(
            "ALLOWED_CORS_ORIGINS",
            ["http://localhost:3000", "http://localhost:8000", "http://localhost:5006", "http://0.0.0.0:5006"],
            list[str],
        )
    )
    TEMP_DIR: Path | None = field(default_factory=get_env("TEMP_DIR", None))

    def get_csrf_config(self) -> "CSRFConfig":
        from litestar.config.csrf import CSRFConfig
        return CSRFConfig(
            secret=self.SECRET_KEY,
            cookie_secure=self.CSRF_COOKIE_SECURE,
            cookie_name=self.CSRF_COOKIE_NAME,
            header_name=self.CSRF_HEADER_NAME,
        )

    def get_cors_config(self) -> "CORSConfig":
        from litestar.config.cors import CORSConfig
        return CORSConfig(allow_origins=self.ALLOWED_CORS_ORIGINS)

    def get_compression_config(self) -> "CompressionConfig":
        from litestar.config.compression import CompressionConfig
        return CompressionConfig(backend="gzip")

    def get_problem_details_config(self) -> "ProblemDetailsConfig":
        from litestar.exceptions import HTTPException
        from litestar.plugins.problem_details import ProblemDetailsConfig
        from sqlspec.exceptions import UniqueViolationError
        from cymbal.lib.exceptions import (
            ConflictError, NotFoundError, PasswordValidationError,
            ValidationError, conflict_error_to_problem_details,
            http_exception_to_problem_details, not_found_error_to_problem_details,
            unique_violation_to_problem_details, validation_error_to_problem_details,
        )

        return ProblemDetailsConfig(
            enable_for_all_http_exceptions=True,
            exception_to_problem_detail_map={
                HTTPException: http_exception_to_problem_details,
                ValidationError: validation_error_to_problem_details,
                PasswordValidationError: validation_error_to_problem_details,
                NotFoundError: not_found_error_to_problem_details,
                ConflictError: conflict_error_to_problem_details,
                UniqueViolationError: unique_violation_to_problem_details,
            },
        )


@dataclass
class AuthSettings:
    """Authentication configuration settings."""
    # Placeholder for future expansion
    pass


@dataclass
class ViteSettings:
    """Vite development server and build configuration."""

    DEV_MODE: bool = field(default_factory=get_env("VITE_DEV_MODE", False))
    ASSET_URL: str = field(default_factory=get_env("ASSET_URL", "/static/"))

    @property
    def set_static_files(self) -> bool:
        return self.ASSET_URL.startswith("/")

    def get_config(self) -> "ViteConfig":
        from litestar_vite import PathConfig, RuntimeConfig, TypeGenConfig, ViteConfig

        return ViteConfig(
            mode="spa",
            dev_mode=self.DEV_MODE,
            paths=PathConfig(
                root=BASE_DIR.parent.parent / "js" / "web", # Assuming future structure, may need adjustment
                bundle_dir=Path(BASE_DIR / "server" / "static"),
                asset_url=self.ASSET_URL,
            ),
            runtime=RuntimeConfig(executor="bun"),
            types=TypeGenConfig(output=Path("src/lib/generated")),
        )


@dataclass
class ChannelSettings:
    """Configuration for Litestar Channels (WebSockets)."""
    BACKEND_URL: str = field(default_factory=get_env("CHANNELS_BACKEND_URL", "memory"))
    HISTORY_TTL: int = field(default_factory=get_env("CHANNELS_HISTORY_TTL", 60))

    def get_config(self) -> "ChannelsPlugin":
        from litestar.channels import ChannelsPlugin
        from litestar.channels.backends.memory import MemoryChannelsBackend
        return ChannelsPlugin(backend=MemoryChannelsBackend(history=self.HISTORY_TTL), arbitrary_channels_allowed=True)


# --- Vertex AI Demo Specific Settings ---

@dataclass
class VertexAISettings:
    """Vertex AI configuration settings."""

    PROJECT_ID: str = field(
        default_factory=lambda: get_config_val(
            "VERTEX_AI_PROJECT_ID", get_config_val("GOOGLE_PROJECT_ID", "")
        )
    )
    LOCATION: str = field(default_factory=get_env("VERTEX_AI_LOCATION", "us-central1"))
    API_KEY: str | None = field(
        default_factory=lambda: get_config_val(
            "VERTEX_AI_API_KEY",
            get_config_val(
                "GOOGLE_AI_API_KEY",
                get_config_val("GOOGLE_API_KEY", get_config_val("GENAI_API_KEY", None)),
            ),
        )
    )
    EMBEDDING_MODEL: str = field(
        default_factory=lambda: get_config_val(
            "VERTEX_AI_EMBEDDING_MODEL", get_config_val("EMBEDDING_MODEL", "text-embedding-004")
        )
    )
    EMBEDDING_DIMENSIONS: int = field(default_factory=get_env("VERTEX_AI_EMBEDDING_DIMENSIONS", 768))
    CHAT_MODEL: str = field(
        default_factory=lambda: get_config_val(
            "VERTEX_AI_CHAT_MODEL", get_config_val("GEMINI_MODEL", "gemini-2.5-flash-lite")
        )
    )

    # Context Caching Settings
    CACHE_TTL_SECONDS: int = field(default_factory=get_env("VERTEX_AI_CACHE_TTL_SECONDS", 3600))
    CACHE_PREFIX: str = field(default_factory=get_env("VERTEX_AI_CACHE_PREFIX", "cymbal-coffee"))

    # Streaming Settings
    STREAM_BUFFER_SIZE: int = field(default_factory=get_env("VERTEX_AI_STREAM_BUFFER_SIZE", 1024))
    STREAM_TIMEOUT_SECONDS: int = field(default_factory=get_env("VERTEX_AI_STREAM_TIMEOUT_SECONDS", 30))


@dataclass
class AgentSettings:
    """Agent system configuration."""

    INTENT_THRESHOLD: float = field(default_factory=get_env("AGENT_INTENT_THRESHOLD", 0.8))
    VECTOR_SEARCH_THRESHOLD: float = field(default_factory=get_env("AGENT_VECTOR_SEARCH_THRESHOLD", 0.7))
    VECTOR_SEARCH_LIMIT: int = field(default_factory=get_env("AGENT_VECTOR_SEARCH_LIMIT", 5))
    CONVERSATION_HISTORY_LIMIT: int = field(default_factory=get_env("AGENT_CONVERSATION_HISTORY_LIMIT", 10))
    SESSION_EXPIRE_HOURS: int = field(default_factory=get_env("AGENT_SESSION_EXPIRE_HOURS", 24))


@dataclass
class CacheSettings:
    """Caching configuration."""

    RESPONSE_TTL_MINUTES: int = field(default_factory=get_env("CACHE_RESPONSE_TTL_MINUTES", 5))
    EMBEDDING_CACHE_ENABLED: bool = field(default_factory=get_env("CACHE_EMBEDDING_ENABLED", True))


@dataclass
class Settings:
    """Main settings container."""

    app: AppSettings = field(default_factory=AppSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    etl: ETLSettings = field(default_factory=ETLSettings)
    collector: CollectorSettings = field(default_factory=CollectorSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    email: EmailSettings = field(default_factory=EmailSettings)
    vite: ViteSettings = field(default_factory=ViteSettings)
    channels: ChannelSettings = field(default_factory=ChannelSettings)
    gcp: GoogleCloudSettings = field(default_factory=GoogleCloudSettings)
    task: TaskSettings = field(default_factory=TaskSettings)
    
    # AI specific
    vertex_ai: VertexAISettings = field(default_factory=VertexAISettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.app.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.collector.DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.etl.get_working_path().mkdir(parents=True, exist_ok=True)
        if self.app.TEMP_DIR:
            self.app.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def setup_litestar_env(self) -> None:
        """Setup environment variables required by Litestar and granian."""
        os.environ.setdefault("LITESTAR_APP", "cymbal.server.asgi:create_app")
        os.environ.setdefault("LITESTAR_APP_NAME", self.app.NAME)
        os.environ.setdefault("LITESTAR_GRANIAN_IN_SUBPROCESS", "false")
        os.environ.setdefault("LITESTAR_GRANIAN_USE_LITESTAR_LOGGER", "true")

    @classmethod
    @lru_cache(maxsize=1, typed=True)
    def from_env(cls, dotenv_filename: str = ".env") -> "Settings":
        """Load settings from environment with optional .env file support."""
        from litestar.cli._utils import console

        env_file = Path.cwd() / dotenv_filename
        if env_file.exists():
            from dotenv import load_dotenv
            # console.print(f"[yellow]Loading environment configuration from {dotenv_filename}[/]")
            load_dotenv(env_file, override=True)
        
        settings = cls()
        settings.setup_litestar_env()
        return settings


def get_settings(dotenv_filename: str = ".env") -> Settings:
    """Get application settings."""
    return Settings.from_env(dotenv_filename)