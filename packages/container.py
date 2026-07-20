"""
packages/container.py

Application service container.
"""

from __future__ import annotations


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