from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.infrastructure.ai.manager import LLMManager
from packages.infrastructure.ai.registry import LLMRegistry


class AIContainer(
    containers.DeclarativeContainer,
):

    settings = providers.DependenciesContainer()

    registry = providers.Singleton(
        LLMRegistry,
    )

    manager = providers.Singleton(
        LLMManager,
    )