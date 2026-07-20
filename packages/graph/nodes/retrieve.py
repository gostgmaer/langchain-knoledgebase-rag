"""
packages/graph/nodes/retrieve.py
"""

from __future__ import annotations

from packages.graph.state import GraphState
from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.schemas import SearchRequest


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

        response = await self._knowledge.search(
            SearchRequest(
                query=query,
                tenant_id=state["tenant_id"],
                top_k=5,
            )
        )

        state["context"] = [
            result.document
            for result in response.results
        ]

        return state