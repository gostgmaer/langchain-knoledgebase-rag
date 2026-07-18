# Base tool
from __future__ import annotations

from abc import ABC
from abc import abstractmethod


class BaseInternalTool(ABC):

    name: str

    description: str

    @abstractmethod
    async def execute(
        self,
        **kwargs,
    ):
        ...