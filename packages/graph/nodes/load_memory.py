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
    ) -> dict:
        """
        Returns a partial update (`{"memories": [...]}`), not the whole
        mutated `state` object. Mutating and returning the full state
        happened to work under the graph's old strictly-sequential
        topology (only one node ever ran per step, so there was never
        a second write to reconcile it against) but broke the moment
        `planner` started running concurrently with this node
        (packages/graph/builder.py's `planner`/`load_memory` fan-out):
        LangGraph read this node's full-state return as a competing
        write to every key in it, including `rewritten_query` — a key
        this node never actually sets — and raised `InvalidUpdateError`
        ("Can receive only one value per step") since planner was
        writing that same key in the same step. Every node should
        return only the keys it actually changed.
        """

        query = state["messages"][-1].content

        response = await self._memory.search(
            SearchMemoryRequest(
                query=query,
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
            )
        )

        return {
            "memories": [
                result.memory
                for result in response.results
            ]
        }