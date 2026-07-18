# Tools manager
from langchain_core.tools import BaseTool

from .registry import ToolRegistry


class ToolManager:

    def __init__(self):
        self._tools = ToolRegistry.get_tools()

    @property
    def tools(self) -> list[BaseTool]:
        return self._tools

    def bind(self, llm):
        return llm.bind_tools(self._tools)