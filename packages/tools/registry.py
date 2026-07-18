# Tools registry
from __future__ import annotations

from langchain_core.tools import BaseTool


class ToolRegistry:

    def __init__(self):

        self._tools: dict[
            str,
            BaseTool,
        ] = {}

    def register(
        self,
        tool: BaseTool,
    ) -> None:

        self._tools[tool.name] = tool

    def get(
        self,
        name: str,
    ) -> BaseTool:

        return self._tools[name]

    def list(self):

        return list(self._tools.values())
