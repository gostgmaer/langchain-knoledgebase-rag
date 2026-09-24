"""
packages/graph/nodes/writer.py
"""

from __future__ import annotations

from packages.chat.chat_service import ChatService
from packages.chat.request import ChatRequest
from packages.graph.state import GraphState
from packages.prompts.builder import PromptBuilder
from packages.shared.messages import normalize_message_content, sanitize_tool_call_args


class WriterNode:
    """
    Synthesizes every sub-question's research finding (ResearcherNode's
    output) into one coherent, comparative final answer — the actual
    fix for Multi-Agent's driving gap: today's single retrieve+llm pass
    blends sources or misses angles on a multi-part question, since it
    never decomposes into independent sub-investigations first.

    No tools bound — pure synthesis over already-gathered findings, not
    a fresh retrieval/tool-calling turn. Output satisfies the same
    contract LLMNode already guarantees (appends a real AIMessage to
    state["messages"], sets state["usage"]) so
    ChatService._finalize_or_pause needs no changes to persist it.
    """

    def __init__(
        self,
        chat_service: ChatService,
        prompt_builder: PromptBuilder,
    ) -> None:
        self._chat = chat_service
        self._builder = prompt_builder

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        findings = state.get("research_findings") or []

        synthesis_context = [
            f"Sub-question: {finding.sub_question}\nFinding: {finding.finding}"
            for finding in findings
        ]

        system_prompt = (
            f"{state['system_prompt']}\n\n"
            "You have already researched each part of the user's "
            "question independently — the sections below are your own "
            "findings, one per sub-question. Synthesize them into one "
            "cohesive answer that addresses every sub-question "
            "distinctly, rather than blending them together."
        )

        prompt = self._builder.build(
            system_prompt=system_prompt,
            memories=state.get("memories") or [],
            context=synthesis_context,
            messages=state["messages"],
        )

        request = ChatRequest(
            conversation_id=state["conversation_id"],
            messages=prompt,
            tools=[],
        )

        response = await self._chat.chat(request)

        response.message.content = normalize_message_content(response.message.content)
        sanitize_tool_call_args(response.message)

        state["messages"].append(response.message)
        state["usage"] = response.usage or {}

        # Deduped by chunk, keeping the higher score — unlike
        # RetrieveNode's own multi-query fan-out (which merges by
        # chunk.id before it ever reaches citations), each sub-question
        # here runs its own independent research subgraph with no
        # visibility into what the others retrieved, so the same real
        # chunk commonly gets pulled into more than one sub-question's
        # findings (confirmed live: a two-part question against a
        # single-document knowledge base cited the same chunk twice,
        # once per sub-question, with two different rerank scores).
        # Same "keep the higher of the two scores" idiom as
        # MultiVectorRetriever's own dedup.
        deduped: dict[tuple, object] = {}
        for finding in findings:
            for citation in finding.citations:
                key = (citation.document_id, citation.chunk_id)
                existing = deduped.get(key)
                if existing is None or citation.score > existing.score:
                    deduped[key] = citation
        state["citations"] = list(deduped.values())

        state["context"] = synthesis_context

        return state
