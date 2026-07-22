# Container tools setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.tools.builtin.calculator import calculator
from packages.tools.executor import ToolExecutor
from packages.tools.manager import ToolManager
from packages.tools.registry import ToolRegistry
from packages.tools.builtin.weather import get_weather
from packages.tools.builtin.news import get_news
from packages.tools.builtin.search import get_google_search
from packages.tools.builtin.knowledge_base import (
    make_document_search_tool,
    make_knowledge_base_search_tool,
)
from packages.knowledge.manager import KnowledgeManager


def init_tool_manager(
    registry: ToolRegistry,
    executor: ToolExecutor,
    knowledge_manager: KnowledgeManager,
) -> ToolManager:
    manager = ToolManager(registry=registry, executor=executor)
    manager.register(get_weather)
    manager.register(get_news)
    manager.register(get_google_search)
    manager.register(calculator)
    manager.register(make_knowledge_base_search_tool(knowledge_manager))
    manager.register(make_document_search_tool(knowledge_manager))
    return manager


class ToolsContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()

    # rag.knowledge_manager is itself providers.Factory (it depends on
    # repositories bound to a per-request database session)
    rag = providers.DependenciesContainer()


    registry = providers.Factory(
        ToolRegistry,
    )

    executor = providers.Factory(
        ToolExecutor,
        registry=registry,
    )

    manager = providers.Factory(
        init_tool_manager,
        registry=registry,
        executor=executor,
        knowledge_manager=rag.knowledge_manager,
    )