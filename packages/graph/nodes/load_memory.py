from __future__ import annotations

from packages.memory.manager import MemoryManager
from packages.memory.schemas import SearchMemoryRequest


class LoadMemoryNode:

    def __init__(
        self,
        memory_manager: MemoryManager,
    ):
        self._memory = memory_manager

    async def __call__(
        self,
        state,
    ):

        query = state["messages"][-1].content

        response = await self._memory.search(
            SearchMemoryRequest(
                query=query,
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
            )
        )

        state["memories"] = [
            result.memory
            for result in response.results
        ]

        return state