# Memory store
from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from packages.memory.types import Checkpoint


class CheckpointStore(ABC):

    @abstractmethod
    async def save(
        self,
        checkpoint: Checkpoint,
    ) -> None:
        ...

    @abstractmethod
    async def load(
        self,
        thread_id: str,
    ) -> Checkpoint | None:
        ...

    @abstractmethod
    async def delete(
        self,
        thread_id: str,
    ) -> None:
        ...