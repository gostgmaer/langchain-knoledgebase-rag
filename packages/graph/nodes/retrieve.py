"""
packages/graph/nodes/retrieve.py
"""

from __future__ import annotations

from packages.config.loader import settings
from packages.graph.state import GraphState
from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.reranking.cross_encoder import CrossEncoderReranker
from packages.knowledge.schemas import Citation
from packages.knowledge.schemas import SearchResult as FlatSearchResult
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions

# Candidate pool fetched per sub-query, before merge + rerank narrows
# down to settings.rag.max_results.
CANDIDATE_LIMIT = 10


class RetrieveNode:
    """
    Retrieves relevant knowledge for the current user query.

    Responsibilities:
    - Search the knowledge base using the planner's rewritten/expanded
      queries (falling back to the raw last message if the planner
      didn't run or found no query to rewrite)
    - Merge and dedupe multi-query results by chunk id
    - Rerank the merged candidates via a cross-encoder
    - Update graph state with context, flat search results, and
      citations

    This node does not build prompts or invoke the LLM.
    """

    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
        reranker: CrossEncoderReranker,
    ) -> None:
        self._knowledge = knowledge_manager
        self._reranker = reranker

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        primary_query = state.get("rewritten_query") or state["messages"][-1].content
        queries = [primary_query, *state.get("expanded_queries", [])]

        filters = SearchFilter(
            tenant_id=state["tenant_id"],
            model_profile_id=state["model_profile_id"],
        )

        merged: dict[object, object] = {}

        for query in queries:
            results = await self._knowledge.search(
                query=query,
                filters=filters,
                options=SearchOptions(limit=CANDIDATE_LIMIT),
            )

            for result in results:
                existing = merged.get(result.chunk.id)
                if existing is None or result.score > existing.score:
                    merged[result.chunk.id] = result

        candidates = list(merged.values())

        top_k = settings.rag.max_results

        reranked = await self._reranker.rerank(
            primary_query,
            candidates,
            top_k=top_k,
        )

        state["context"] = [result.chunk.content for result in reranked]

        state["search_results"] = [
            FlatSearchResult(
                document_id=result.chunk.document_id,
                chunk_id=result.chunk.id,
                chunk_index=result.chunk.chunk_index,
                content=result.chunk.content,
                score=result.score,
            )
            for result in reranked
        ]

        state["citations"] = [
            Citation(
                document_id=result.chunk.document_id,
                chunk_id=result.chunk.id,
                chunk_index=result.chunk.chunk_index,
                score=result.score,
            )
            for result in reranked
        ]

        return state
