"""
packages/graph/nodes/extract_memory.py
"""

from __future__ import annotations

from packages.graph.state import GraphState
from packages.memory.manager import MemoryManager


class ExtractMemoryNode:
    """
    Extracts long-term memories from the completed conversation.
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
    ) -> None:
        self._memory = memory_manager

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        await self._memory.extract(
            conversation_id=state["conversation_id"],
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            messages=state["messages"],
        )

        return state