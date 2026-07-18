# Graph checkpoint
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from packages.memory.manager import MemoryManager


class GraphCheckpointFactory:

    def __init__(
        self,
        memory: MemoryManager,
    ) -> None:
        self.memory = memory

    def create(self):

        #
        # Later:
        #
        # RedisSaver
        # PostgreSQLSaver
        # MongoSaver
        #

        return MemorySaver()