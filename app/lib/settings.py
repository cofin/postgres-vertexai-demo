"""Application settings management following SQLStack pattern."""

from __future__ import annotations

import binascii
import json
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, cast

from litestar.data_extractors import RequestExtractorField

from app.utils.env import get_env

if TYPE_CHECKING:
    from collections.abc import Callable

    from litestar.data_extractors import ResponseExtractorField

DEFAULT_MODULE_NAME = "app"
BASE_DIR = Path(__file__).parent.parent
SERVER_DIR = Path(BASE_DIR / "server")
STATIC_DIR = Path(SERVER_DIR / "static")
TEMPLATE_DIR = Path(SERVER_DIR / "templates")


@dataclass
class DatabaseSettings:
    """Database configuration settings."""

    ECHO: bool = field(default_factory=get_env("DATABASE_ECHO", False))
    """Enable database query logs."""
    POOL_MIN_SIZE: int = field(default_factory=get_env("DATABASE_POOL_MIN_SIZE", 2))
    """Min size for database connection pool"""
    POOL_MAX_SIZE: int = field(default_factory=get_env("DATABASE_POOL_MAX_SIZE", 10))
    """Max size for database connection pool"""
    POOL_TIMEOUT: int = field(default_factory=get_env("DATABASE_POOL_TIMEOUT", 30))
    """Time in seconds for timing connections out of the connection pool."""
    POOL_RECYCLE: int = field(default_factory=get_env("DATABASE_POOL_RECYCLE", 3600))
    """Amount of time to wait before recycling connections."""
    URL: str = field(default_factory=get_env("DATABASE_URL", "postgresql://app:app@localhost:15432/app"))
    """Database URL."""
    MIGRATION_PATH: str = field(default_factory=get_env("DATABASE_MIGRATION_PATH", f"{BASE_DIR}/db/migrations"))
    """The path to database migrations."""
    FIXTURE_PATH: str = field(default_factory=get_env("DATABASE_FIXTURE_PATH", f"{BASE_DIR}/db/fixtures"))
    """The path to JSON fixture files to load into tables."""


@dataclass
class VertexAISettings:
    """Vertex AI configuration settings."""

    PROJECT_ID: str = field(default_factory=get_env("VERTEX_AI_PROJECT_ID", ""))
    """Google Cloud Project ID for Vertex AI."""
    LOCATION: str = field(default_factory=get_env("VERTEX_AI_LOCATION", "us-central1"))
    """Vertex AI location/region."""
    EMBEDDING_MODEL: str = field(default_factory=get_env("VERTEX_AI_EMBEDDING_MODEL", "text-embedding-004"))
    """Vertex AI embedding model."""
    EMBEDDING_DIMENSIONS: int = field(default_factory=get_env("VERTEX_AI_EMBEDDING_DIMENSIONS", 768))
    """Embedding vector dimensions."""
    CHAT_MODEL: str = field(default_factory=get_env("VERTEX_AI_CHAT_MODEL", "gemini-2.5-flash-lite"))
    """Vertex AI chat model."""

    # Context Caching Settings
    CACHE_TTL_SECONDS: int = field(default_factory=get_env("VERTEX_AI_CACHE_TTL_SECONDS", 3600))
    """Context cache TTL in seconds (default: 1 hour)."""
    CACHE_PREFIX: str = field(default_factory=get_env("VERTEX_AI_CACHE_PREFIX", "cymbal-coffee"))
    """Prefix for cache names."""

    # Streaming Settings
    STREAM_BUFFER_SIZE: int = field(default_factory=get_env("VERTEX_AI_STREAM_BUFFER_SIZE", 1024))
    """Buffer size for streaming responses."""
    STREAM_TIMEOUT_SECONDS: int = field(default_factory=get_env("VERTEX_AI_STREAM_TIMEOUT_SECONDS", 30))
    """Timeout for streaming responses."""


@dataclass
class AgentSettings:
    """Agent system configuration."""

    INTENT_THRESHOLD: float = field(default_factory=get_env("AGENT_INTENT_THRESHOLD", 0.8))
    """Intent detection confidence threshold."""
    VECTOR_SEARCH_THRESHOLD: float = field(default_factory=get_env("AGENT_VECTOR_SEARCH_THRESHOLD", 0.7))
    """Vector search similarity threshold."""
    VECTOR_SEARCH_LIMIT: int = field(default_factory=get_env("AGENT_VECTOR_SEARCH_LIMIT", 5))
    """Maximum number of vector search results."""
    CONVERSATION_HISTORY_LIMIT: int = field(default_factory=get_env("AGENT_CONVERSATION_HISTORY_LIMIT", 10))
    """Maximum conversation history to maintain."""
    SESSION_EXPIRE_HOURS: int = field(default_factory=get_env("AGENT_SESSION_EXPIRE_HOURS", 24))
    """Session expiration in hours."""


@dataclass
class CacheSettings:
    """Caching configuration."""

    RESPONSE_TTL_MINUTES: int = field(default_factory=get_env("CACHE_RESPONSE_TTL_MINUTES", 5))
    """Response cache TTL in minutes."""
    EMBEDDING_CACHE_ENABLED: bool = field(default_factory=get_env("CACHE_EMBEDDING_ENABLED", True))
    """Enable embedding caching."""


@dataclass
class LogSettings:
    """Logger configuration."""

    # https://stackoverflow.com/a/1845097/6560549
    EXCLUDE_PATHS: str = r"\A(?!x)x"
    """Regex to exclude paths from logging."""
    INCLUDE_COMPRESSED_BODY: bool = False
    """Include 'body' of compressed responses in log output."""
    LEVEL: int = field(default_factory=get_env("LOG_LEVEL", 30))
    """Stdlib log levels.

    Only emit logs at this level, or higher.
    """
    OBFUSCATE_COOKIES: set[str] = field(default_factory=lambda: {"session", "XSRF-TOKEN"})
    """Request cookie keys to obfuscate."""
    OBFUSCATE_HEADERS: set[str] = field(default_factory=lambda: {"Authorization", "X-API-KEY", "X-XSRF-TOKEN"})
    """Request header keys to obfuscate."""
    REQUEST_FIELDS: list[RequestExtractorField] = field(
        default_factory=get_env(
            "LOG_REQUEST_FIELDS",
            [
                "path",
                "method",
                "query",
                "path_params",
            ],
            list[RequestExtractorField],
        ),
    )
    """Attributes of the Request to be logged."""
    RESPONSE_FIELDS: list[ResponseExtractorField] = field(
        default_factory=cast(
            "Callable[[],list[ResponseExtractorField]]",
            get_env(
                "LOG_RESPONSE_FIELDS",
                ["status_code"],
            ),
        ),
    )
    """Attributes of the Response to be logged."""
    SQLSPEC_LEVEL: int = field(default_factory=get_env("SQLSPEC_LOG_LEVEL", 30))
    """Level to log SQLSpec logs."""
    SQLGLOT_LEVEL: int = field(default_factory=get_env("SQLGLOT_LOG_LEVEL", 40))
    """Level to log SQLGlot logs."""
    ASGI_ACCESS_LEVEL: int = field(default_factory=get_env("ASGI_ACCESS_LOG_LEVEL", 30))
    """Level to log uvicorn access logs."""
    ASGI_ERROR_LEVEL: int = field(default_factory=get_env("ASGI_ERROR_LOG_LEVEL", 30))
    """Level to log uvicorn error logs."""


@dataclass
class AppSettings:
    """Application configuration."""

    NAME: str = field(default_factory=lambda: "PostgreSQL + Vertex AI Demo")
    """Application name."""
    VERSION: str = field(default="0.3.0")
    """Current application version."""
    DEBUG: bool = field(default_factory=get_env("DEBUG", False))
    """Run application with debug mode."""
    SECRET_KEY: str = field(
        default_factory=get_env("SECRET_KEY", binascii.hexlify(os.urandom(32)).decode(encoding="utf-8")),
    )
    """Application secret key."""
    STATIC_DIR: Path = field(default_factory=get_env("STATIC_DIR", STATIC_DIR))
    """Default URL where static assets are located."""
    TEMPLATE_DIR: Path = field(default_factory=get_env("TEMPLATE_DIR", TEMPLATE_DIR))
    """Template directory path."""
    ALLOWED_CORS_ORIGINS: list[str] | str = field(default_factory=get_env("ALLOWED_CORS_ORIGINS", ["*"], list[str]))
    """Allowed CORS Origins"""
    CSRF_COOKIE_NAME: str = field(default_factory=get_env("CSRF_COOKIE_NAME", "XSRF-TOKEN"))
    """CSRF Cookie Name"""
    SESSION_MAX_AGE: int = field(default_factory=get_env("SESSION_MAX_AGE", 86400 * 7))
    """Session cookie max age in seconds (default: 7 days)"""
    CSRF_HEADER_NAME: str = field(default_factory=get_env("CSRF_HEADER_NAME", "X-XSRF-TOKEN"))
    """CSRF Header Name"""
    CSRF_COOKIE_SECURE: bool = field(default_factory=get_env("CSRF_COOKIE_SECURE", False))
    """CSRF Secure Cookie"""
    ENV_SECRETS: str = field(default_factory=get_env("ENV_SECRETS", "runtime-secrets"))
    """Path to environment secrets."""

    def __post_init__(self) -> None:
        if isinstance(self.ALLOWED_CORS_ORIGINS, str):
            if self.ALLOWED_CORS_ORIGINS.startswith("[") and self.ALLOWED_CORS_ORIGINS.endswith("]"):
                try:
                    self.ALLOWED_CORS_ORIGINS = json.loads(self.ALLOWED_CORS_ORIGINS)  # pyright: ignore[reportConstantRedefinition]
                except (SyntaxError, ValueError):
                    msg = "ALLOWED_CORS_ORIGINS is not a valid list representation."
                    raise ValueError(msg) from None
            else:
                self.ALLOWED_CORS_ORIGINS = [host.strip() for host in self.ALLOWED_CORS_ORIGINS.split(",")]  # pyright: ignore[reportConstantRedefinition]


@dataclass
class Settings:
    """Main application settings."""

    app: AppSettings = field(default_factory=AppSettings)
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    vertex_ai: VertexAISettings = field(default_factory=VertexAISettings)
    agents: AgentSettings = field(default_factory=AgentSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    log: LogSettings = field(default_factory=LogSettings)

    @classmethod
    @lru_cache(maxsize=1, typed=True)
    def from_env(cls, dotenv_filename: str = ".env") -> Settings:
        from dotenv import load_dotenv

        env_file = Path(f"{os.curdir}/{dotenv_filename}")
        env_file_exists = env_file.is_file()
        if env_file_exists:
            import structlog

            logger = structlog.get_logger()
            load_dotenv(env_file, override=True)

        try:
            database: DatabaseSettings = DatabaseSettings()
            app: AppSettings = AppSettings()
            vertex_ai: VertexAISettings = VertexAISettings()
            agents: AgentSettings = AgentSettings()
            cache: CacheSettings = CacheSettings()
            log: LogSettings = LogSettings()
        except (ValueError, TypeError, KeyError) as e:
            import structlog

            logger = structlog.get_logger()
            logger.fatal("Could not load settings", error=str(e))
            sys.exit(1)

        return Settings(app=app, db=database, vertex_ai=vertex_ai, agents=agents, cache=cache, log=log)


def get_settings(dotenv_filename: str = ".env") -> Settings:
    """Get application settings."""
    return Settings.from_env(dotenv_filename)
