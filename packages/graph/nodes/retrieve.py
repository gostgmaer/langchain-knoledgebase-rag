"""
packages/graph/nodes/retrieve.py
"""

from __future__ import annotations

from packages.graph.state import GraphState
from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.vectorstores.schema import SearchFilter


class RetrieveNode:
    """
    Retrieves relevant knowledge for the current user query.

    Responsibilities:
    - Search the knowledge base
    - Update graph state with retrieved context

    This node does not build prompts or invoke the LLM.
    """

    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
    ) -> None:
        self._knowledge = knowledge_manager

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        query = state["messages"][-1].content

        results = await self._knowledge.search(
            query=query,
            filters=SearchFilter(
                tenant_id=state["tenant_id"],
                model_profile_id=state["model_profile_id"],
            ),
        )

        state["context"] = [
            result.chunk.content
            for result in results
        ]

        return state
