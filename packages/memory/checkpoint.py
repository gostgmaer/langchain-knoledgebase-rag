# Checkpointing logic
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from packages.memory.strategy import MemoryStrategy


class CheckpointFactory:

    def __init__(
        self,
        strategy: MemoryStrategy,
    ) -> None:
        self.strategy = strategy

    def create(self) -> BaseCheckpointSaver:

        if self.strategy == MemoryStrategy.MEMORY:
            return MemorySaver()

        #
        # Future
        #

        # if strategy == REDIS:
        #     return RedisCheckpointSaver()

        # if strategy == POSTGRES:
        #     return PostgresCheckpointSaver()

        raise ValueError(
            f"Unsupported strategy: {self.strategy}"
        )