"""A scalable, auto-wiring Service Locator for dependency injection."""

from __future__ import annotations

import inspect
from typing import Any, Type, TypeVar

from sqlspec.driver import AsyncDriverAdapterBase

from app.services.base import SQLSpecService
from app.services.vertex_ai import VertexAIService

T = TypeVar("T")


class ServiceLocator:
    """
    A scalable service locator that uses introspection to automatically
    resolve and inject dependencies based on type hints.
    """

    def __init__(self) -> None:
        """Initializes the service locator."""
        self._cache: dict[Type, Any] = {}
        self._singletons: set[Type] = {VertexAIService}

    def get(self, service_cls: Type[T], session: AsyncDriverAdapterBase | None) -> T:
        """
        Get an instance of a service, resolving its dependencies automatically.

        Args:
            service_cls: The class of the service to instantiate.
            session: The active database session, required for services
                     that interact with the database.

        Returns:
            An instance of the requested service.
        """
        # Import here to avoid circular imports
        from app.services.adk.tool_service import AgentToolsService
        from app.services.intent import IntentService

        # 1. Handle Singletons: If the class is marked as a singleton,
        # return a cached instance or create and cache it.
        if service_cls in self._singletons:
            if service_cls not in self._cache:
                # Singletons are created without a session.
                self._cache[service_cls] = self._create_instance(service_cls, None)
            return self._cache[service_cls]

        # 2. Handle complex services with special dependency injection needs
        if service_cls == IntentService:
            from app.services.exemplar import ExemplarService
            return IntentService(
                driver=session,
                exemplar_service=self.get(ExemplarService, session),
                vertex_ai_service=self.get(VertexAIService, session)
            )

        if service_cls == AgentToolsService:
            from app.services.product import ProductService
            from app.services.chat import ChatService
            from app.services.metrics import MetricsService
            return AgentToolsService(
                driver=session,
                product_service=self.get(ProductService, session),
                chat_service=self.get(ChatService, session),
                metrics_service=self.get(MetricsService, session),
                intent_service=self.get(IntentService, session),
                vertex_ai_service=self.get(VertexAIService, session),
            )

        # 3. Handle Transient (session-scoped) services.
        if session is None:
            raise ValueError(
                f"A database session is required to create a transient instance of {service_cls.__name__}"
            )

        return self._create_instance(service_cls, session)

    def _create_instance(
        self, service_cls: Type[T], session: AsyncDriverAdapterBase | None
    ) -> T:
        """
        Creates an instance of a class by inspecting its __init__ method
        and recursively resolving dependencies.
        """
        # Get the constructor signature
        try:
            signature = inspect.signature(service_cls.__init__)
        except (TypeError, ValueError):
            return service_cls()  # type: ignore[call-arg]

        dependencies: dict[str, Any] = {}
        # Iterate over constructor parameters, skipping 'self'
        for param in list(signature.parameters.values())[1:]:
            param_type = param.annotation

            if param_type is inspect.Parameter.empty:
                raise TypeError(
                    f"Cannot resolve dependency for '{service_cls.__name__}': "
                    f"Parameter '{param.name}' is missing a type hint."
                )

            # 3. Inject the database session/driver if type-hinted
            if (
                isinstance(param_type, type)
                and issubclass(param_type, AsyncDriverAdapterBase)
            ) or param.name in ("driver", "session"):
                dependencies[param.name] = session

            # 4. Recursively resolve other service dependencies
            else:
                dependencies[param.name] = self.get(param_type, session)

        # 5. Create and return the instance with resolved dependencies
        return service_cls(**dependencies)
