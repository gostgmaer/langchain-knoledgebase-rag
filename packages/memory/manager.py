# Memory manager
from .checkpoint import CheckpointManager


class MemoryManager:

    def __init__(self):
        self._checkpoint = CheckpointManager()

    @property
    def checkpointer(self):
        return self._checkpoint.checkpointer