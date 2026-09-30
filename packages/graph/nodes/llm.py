"""
packages/graph/nodes/llm.py
"""

from __future__ import annotations

from langgraph.config import get_stream_writer

from packages.chat.chat_service import ChatService
from packages.chat.request import ChatRequest
from packages.chat.response import ChatResponse
from packages.domain.enums.model_status import ModelStatus
from packages.graph.state import GraphState
from packages.infrastructure.ai.config import build_llm_config_from_profile
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.prompts.builder import PromptBuilder
from packages.shared.messages import normalize_message_content, sanitize_tool_call_args
from packages.tools.manager import ToolManager


class LLMNode:
    """
    Executes the LLM.

    Responsibilities:
    - Build the prompt
    - Bind available tools
    - Invoke the LLM
    - Update the graph state

    This node does not know how prompts are constructed.
    """

    def __init__(
        self,
        chat_service: ChatService,
        prompt_builder: PromptBuilder,
        tool_manager: ToolManager,
        model_profile_repository: ModelProfileRepository,
    ) -> None:

        self._chat = chat_service
        self._builder = prompt_builder
        self._tools = tool_manager
        self._model_profiles = model_profile_repository

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        prompt = self._builder.build(
            system_prompt=state["system_prompt"],
            memories=state["memories"],
            context=state["context"],
            messages=state["messages"],
        )

        request = ChatRequest(
            conversation_id=state["conversation_id"],
            messages=prompt,
            tools=self._tools.list() if state.get("tools_enabled", True) else [],
            llm_config=await self._resolve_llm_config(state.get("model_profile_id")),
        )

        if state.get("stream"):
            response = await self._stream(
                request, state.get("citations") or [], state.get("retrieval_id")
            )
        else:
            response = await self._chat.chat(request)

        response.message.content = normalize_message_content(response.message.content)
        sanitize_tool_call_args(response.message)

        state["messages"].append(response.message)
        state["usage"] = response.usage or {}

        return state

    async def _resolve_llm_config(self, model_profile_id):
        """
        None means "use ChatService's default LLMManager", same as before
        this existed — a missing id, a deleted profile, a DISABLED/
        DEPRECATED one, or a provider LLMFactory doesn't implement yet
        (build_llm_config_from_profile's own fallback) are all treated the
        same way: fail soft to the global default rather than ever failing
        a chat turn over a model-profile lookup.
        """

        if model_profile_id is None:
            return None

        profile = await self._model_profiles.get(model_profile_id)
        if profile is None or profile.status != ModelStatus.ACTIVE:
            return None

        return build_llm_config_from_profile(profile)

    async def _stream(self, request: ChatRequest, citations: list, retrieval_id=None):
        """
        Streams the LLM response token-by-token, pushing each chunk to
        the graph's stream writer (surfaced over HTTP via
        GraphManager.stream()'s stream_mode="custom"), while still
        assembling and returning the same ChatResponse shape the
        non-streaming path returns — the rest of this node doesn't
        need to know the difference.
        """

        writer = get_stream_writer()
        final = None

        async for chunk in self._chat.astream(request):
            writer({"type": "token", "content": normalize_message_content(chunk.content)})
            final = chunk if final is None else final + chunk

        # The non-streaming path's caller (ChatService._execute_runtime)
        # reads response_metadata/additional_kwargs straight off
        # result["messages"][-1] — but GraphManager.stream()'s
        # stream_mode="custom" only ever surfaces writer events, never
        # the final graph state, so streaming needs this pushed
        # through explicitly or that data is unreachable after the
        # loop ends.
        writer(
            {
                "type": "metadata",
                "response_metadata": getattr(final, "response_metadata", None) or {},
                "additional_kwargs": getattr(final, "additional_kwargs", None) or {},
            }
        )

        # Symmetric to the "metadata" event above and for the same
        # reason — stream_mode="custom" never surfaces the final graph
        # state, so token usage has to be pushed through explicitly or
        # it's unreachable once the stream ends (Token Usage/Cost
        # Tracking, docs/mvpRAG.md v1.1).
        writer(
            {
                "type": "usage",
                "usage": getattr(final, "usage_metadata", None) or {},
            }
        )

        # Same reasoning again, for citations (docs/mvpRAG.md v1.2 —
        # previously a documented, deliberate gap: the streaming path
        # never surfaced retrieval citations at all). `citations` was
        # already computed by the retrieve node earlier in this same
        # turn, before the LLM node ever ran — passed straight through
        # as the raw Citation dataclasses; ChatService (the application
        # layer, which already owns the Citation -> CitationDTO shaping
        # for the non-streaming path) does the dict conversion.
        writer(
            {
                "type": "citations",
                "citations": citations,
                "retrieval_id": str(retrieval_id) if retrieval_id else None,
            }
        )

        return ChatResponse(
            message=final,
            usage=getattr(final, "usage_metadata", None) or {},
        )