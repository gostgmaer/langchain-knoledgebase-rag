"""
packages/graph/nodes/llm.py
"""

from __future__ import annotations

from langgraph.config import get_stream_writer

from packages.graph.state import GraphState
from packages.prompts.builder import PromptBuilder
from packages.chat.chat_service import ChatService
from packages.chat.request import ChatRequest
from packages.chat.response import ChatResponse
from packages.shared.messages import normalize_message_content
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
    ) -> None:

        self._chat = chat_service
        self._builder = prompt_builder
        self._tools = tool_manager

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
        )

        if state.get("stream"):
            response = await self._stream(request)
        else:
            response = await self._chat.chat(request)

        response.message.content = normalize_message_content(response.message.content)

        state["messages"].append(response.message)
        state["usage"] = response.usage or {}

        return state

    async def _stream(self, request: ChatRequest):
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

        return ChatResponse(
            message=final,
            usage=getattr(final, "usage_metadata", None) or {},
        )