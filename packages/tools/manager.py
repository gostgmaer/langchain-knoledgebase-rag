# Tools manager
from __future__ import annotations

from langchain_core.tools import BaseTool

from packages.tools.executor import ToolExecutor
from packages.tools.registry import ToolRegistry


class ToolManager:

    def __init__(
        self,
        registry: ToolRegistry,
        executor: ToolExecutor,
    ):

        self.registry = registry
        self.executor = executor

    def register(
        self,
        tool: BaseTool,
    ):

        self.registry.register(tool)

    def list(self):

        return self.registry.list()

    async def execute(
        self,
        name: str,
        **kwargs,
    ):

        return await self.executor.execute(
            name,
            **kwargs,
        )