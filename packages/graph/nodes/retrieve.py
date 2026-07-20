"""
packages/graph/nodes/retrieve.py
"""

from __future__ import annotations

from packages.graph.state import GraphState
from packages.rag.pipelines.retrieval import RetrievalPipeline
from packages.rag.schemas import RAGRequest


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
        retrieval_pipeline: RetrievalPipeline,
    ) -> None:
        self._retrieval = retrieval_pipeline

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        query = state["messages"][-1].content

        results = await self._retrieval.retrieve(
            RAGRequest(
                tenant_id=state["tenant_id"],
                model_profile_id=state["model_profile_id"],
                query=query,
            )
        )

        state["context"] = [
            result.content
            for result in results
        ]

        return state
