# Tools executor
from __future__ import annotations

from packages.tools.registry import ToolRegistry


class ToolExecutor:

    def __init__(
        self,
        registry: ToolRegistry,
    ):
        self.registry = registry

    async def execute(
        self,
        name: str,
        **kwargs,
    ):

        tool = self.registry.get(name)

        return await tool.ainvoke(kwargs)