# Container memory setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.memory.checkpoint import CheckpointFactory
from packages.memory.manager import MemoryManager
from packages.memory.strategy import MemoryStrategy


class MemoryContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()

    checkpoint = providers.Singleton(
        CheckpointFactory,
        strategy=MemoryStrategy.MEMORY,
    )

    manager = providers.Singleton(
        MemoryManager,
        factory=checkpoint,
    )