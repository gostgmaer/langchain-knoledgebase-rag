# packages/graph/subgraphs/research.py
"""
A small, reusable compiled sub-graph answering one self-contained
sub-question — Subgraphs (docs/mvpRAG.md v2.0), built specifically to
serve Multi-Agent's Researcher role rather than as a decomposition of
the existing single-question graph (which has no motivating pain point
for that).

Deliberately simpler than the parent graph's RetrieveNode/LLMNode: a
sub-question gets no query expansion of its own (ResearcherNode already
fans out one subgraph invocation per sub-question — nothing to expand
at this granularity) and no tool binding (pure research + synthesis,
mirroring IngestionPipeline._generate_summary's one-shot HumanMessage
shape, not the full ChatService pipeline).

Compiled with no checkpointer — one-shot, never independently resumed;
the parent graph's own Postgres checkpoint is what's durable across a
whole conversation turn.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from packages.config.loader import settings
from packages.infrastructure.ai.manager import LLMManager
from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.reranking.cross_encoder import CrossEncoderReranker
from packages.knowledge.schemas import Citation
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions
from packages.shared.messages import normalize_message_content


class ResearchState(TypedDict, total=False):
    """Not GraphState — a minimal, independent state shape for one
    sub-question's research cycle."""

    sub_question: str
    tenant_id: UUID
    model_profile_id: UUID

    context: list[str]
    citations: list[Citation]
    finding: str


class ResearchRetrieveNode:
    """Single-query search + rerank for one sub-question — same
    collaborators RetrieveNode uses, no multi-query fan-out (nothing to
    fan out over at this granularity)."""

    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
        reranker: CrossEncoderReranker,
    ) -> None:
        self._knowledge = knowledge_manager
        self._reranker = reranker

    async def __call__(self, state: ResearchState) -> ResearchState:

        query = state["sub_question"]

        filters = SearchFilter(
            tenant_id=state["tenant_id"],
            model_profile_id=state["model_profile_id"],
        )

        results = await self._knowledge.search(
            query=query,
            filters=filters,
            options=SearchOptions(limit=10),
        )

        top_k = settings.rag.max_results
        reranked = await self._reranker.rerank(query, results, top_k=top_k)

        min_score = settings.rag.min_relevance_score
        reranked = [result for result in reranked if result.score >= min_score]

        state["context"] = [result.chunk.content for result in reranked]
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


class ResearchSynthesizeNode:
    """One bare LLM call answering just the sub-question from just its
    own context — mirrors IngestionPipeline._generate_summary's
    one-shot HumanMessage shape."""

    def __init__(self, llm: LLMManager) -> None:
        self._llm = llm

    async def __call__(self, state: ResearchState) -> ResearchState:

        context = state.get("context") or []
        context_block = "\n\n".join(context) if context else "(no relevant context found)"

        response = await self._llm.ainvoke(
            [
                HumanMessage(
                    content=(
                        "Answer the following sub-question using only the "
                        "context provided. Be concise and specific. If the "
                        "context doesn't answer it, say so plainly.\n\n"
                        f"Sub-question: {state['sub_question']}\n\n"
                        f"Context:\n{context_block}"
                    )
                )
            ]
        )

        state["finding"] = normalize_message_content(response.content)

        return state


class ResearchSubgraphBuilder:

    def __init__(
        self,
        retrieve: ResearchRetrieveNode,
        synthesize: ResearchSynthesizeNode,
    ) -> None:
        self._retrieve = retrieve
        self._synthesize = synthesize

    def build(self) -> CompiledStateGraph[ResearchState, Any, Any]:
        graph = StateGraph(ResearchState)

        graph.add_node("retrieve", self._retrieve)
        graph.add_node("synthesize", self._synthesize)

        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "synthesize")
        graph.add_edge("synthesize", END)

        # No checkpointer — one-shot, never independently resumed; the
        # parent graph's own Postgres checkpoint is what's durable
        # across a whole conversation turn.
        return graph.compile()
