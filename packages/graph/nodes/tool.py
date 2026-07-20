"""
packages/graph/nodes/tool.py
"""

from __future__ import annotations

from langgraph.prebuilt import ToolNode

from packages.tools.manager import ToolManager


class GraphToolNode:
    """
    Executes LLM tool calls.

    This is a thin wrapper around LangGraph's ToolNode.
    """

    def __init__(
        self,
        tool_manager: ToolManager,
    ) -> None:
        self._tool_node = ToolNode(
            tools=tool_manager.list(),
        )

    async def __call__(
        self,
        state,
    ):
        return await self._tool_node.ainvoke(state)