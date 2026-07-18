# Memory manager
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver

from packages.memory.checkpoint import (
    CheckpointFactory,
)


class MemoryManager:

    def __init__(
        self,
        factory: CheckpointFactory,
    ) -> None:

        self._checkpointer = factory.create()

    @property
    def checkpointer(
        self,
    ) -> BaseCheckpointSaver:
        return self._checkpointer