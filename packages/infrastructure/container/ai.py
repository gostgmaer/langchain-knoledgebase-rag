from __future__ import annotations

from dependency_injector import containers, providers

from packages.infrastructure.ai.manager import LLMManager


class AIContainer(
    containers.DeclarativeContainer,
):

    settings = providers.DependenciesContainer()

    manager = providers.Singleton(
        LLMManager,
    )