# Checkpointing logic
from langgraph.checkpoint.memory import InMemorySaver


class CheckpointManager:

    def __init__(self):
        self._checkpointer = InMemorySaver()

    @property
    def checkpointer(self):
        return self._checkpointer