# Container tools setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.tools.executor import ToolExecutor
from packages.tools.manager import ToolManager
from packages.tools.registry import ToolRegistry
from packages.tools.builtin.weather import get_weather
from packages.tools.builtin.news import get_news
from packages.tools.builtin.search import get_google_search


def init_tool_manager(registry: ToolRegistry, executor: ToolExecutor) -> ToolManager:
    manager = ToolManager(registry=registry, executor=executor)
    manager.register(get_weather)
    manager.register(get_news)
    manager.register(get_google_search)
    return manager


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
        init_tool_manager,
        registry=registry,
        executor=executor,
    )