"""
packages/graph/nodes/writer.py
"""

from __future__ import annotations

from langgraph.config import get_stream_writer

from packages.chat.chat_service import LLMChatService
from packages.chat.request import LLMChatRequest
from packages.chat.response import LLMChatResponse
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

    Streams the same way LLMNode does when state["stream"] is set
    (docs/BUGS.md item 60): ChatService.stream() only ever sees
    LangGraph's stream_mode="custom" writer events, never a node's
    final state write directly, so a non-streaming self._chat.chat()
    call here silently threw away every multi-part turn's synthesized
    answer under the real streaming endpoint the UI actually calls —
    chunks stayed empty, and ChatService.stream()'s empty-reply guard
    replaced a genuinely good answer with the generic fallback message
    on every single multi-part/comparison question, every time.
    """

    def __init__(
        self,
        chat_service: LLMChatService,
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

        prompt = await self._builder.build(
            system_prompt=system_prompt,
            memories=state.get("memories") or [],
            context=synthesis_context,
            messages=state["messages"],
        )

        request = LLMChatRequest(
            conversation_id=state["conversation_id"],
            messages=prompt,
            tools=[],
        )

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
        # MultiVectorRetriever's own dedup. Computed before the LLM
        # call (it only depends on `findings`, gathered already by
        # ResearcherNode) so the streaming path below can push it
        # through the writer immediately, the same way LLMNode's
        # already-computed citations arrive as a parameter.
        deduped: dict[tuple, object] = {}
        for finding in findings:
            for citation in finding.citations:
                key = (citation.document_id, citation.chunk_id)
                existing = deduped.get(key)
                if existing is None or citation.score > existing.score:
                    deduped[key] = citation
        citations = list(deduped.values())

        if state.get("stream"):
            response = await self._stream(request, citations)
        else:
            response = await self._chat.chat(request)

        response.message.content = normalize_message_content(response.message.content)
        sanitize_tool_call_args(response.message)

        state["messages"].append(response.message)
        state["usage"] = response.usage or {}
        state["citations"] = citations
        state["context"] = synthesis_context

        return state

    async def _stream(self, request: LLMChatRequest, citations: list):
        """
        Same streaming contract as LLMNode._stream (packages/graph/nodes/llm.py):
        pushes token/metadata/usage/citations events through the graph's stream
        writer, since stream_mode="custom" never surfaces a node's final state
        write — only what it explicitly pushes here. No retrieval_id to push:
        a multi-part turn never had a single one even on the non-streaming path
        (each sub-question runs its own research subgraph independently).
        """

        writer = get_stream_writer()
        final = None

        async for chunk in self._chat.astream(request):
            writer({"type": "token", "content": normalize_message_content(chunk.content)})
            final = chunk if final is None else final + chunk

        writer(
            {
                "type": "metadata",
                "response_metadata": getattr(final, "response_metadata", None) or {},
                "additional_kwargs": getattr(final, "additional_kwargs", None) or {},
            }
        )
        writer(
            {
                "type": "usage",
                "usage": getattr(final, "usage_metadata", None) or {},
            }
        )
        writer(
            {
                "type": "citations",
                "citations": citations,
                "retrieval_id": None,
            }
        )

        return LLMChatResponse(
            message=final,
            usage=getattr(final, "usage_metadata", None) or {},
        )
