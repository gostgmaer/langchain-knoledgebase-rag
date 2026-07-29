"""
packages/container.py

Application service container.
"""

from __future__ import annotations

from dependency_injector import containers, providers

from packages.config.loader import settings as _settings
from packages.shared.logging import configure_logger, get_logger

configure_logger(_settings.logging.level)


class RootContainer(containers.DeclarativeContainer):
    """
    Minimal root container for standalone scripts (e.g. main.py).
    """

    settings = providers.Object(_settings)
    logger = providers.Singleton(get_logger, __name__)


container = RootContainer()


class Container:
    """
    Simple dependency container.
    """

    def __init__(self) -> None:
        self._services: dict[type, object] = {}

    def register(
        self,
        interface: type,
        implementation: object,
    ) -> None:
        self._services[interface] = implementation

    def resolve[T](
        self,
        interface: type[T],
    ) -> T:
        service = self._services.get(interface)

        if service is None:
            raise ValueError(
                f"Service not registered: {interface.__name__}"
            )

        return service