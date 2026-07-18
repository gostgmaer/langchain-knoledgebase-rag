# Container tools setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.tools.executor import ToolExecutor
from packages.tools.manager import ToolManager
from packages.tools.registry import ToolRegistry


class ToolsContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()

    registry = providers.Singleton(
        ToolRegistry,
    )

    executor = providers.Singleton(
        ToolExecutor,
        registry=registry,
    )

    manager = providers.Singleton(
        ToolManager,
        registry=registry,
        executor=executor,
    )