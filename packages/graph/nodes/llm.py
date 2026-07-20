"""
packages/graph/nodes/llm.py
"""

from __future__ import annotations

from packages.graph.state import GraphState
from packages.prompts.builder import PromptBuilder
from packages.chat.chat_service import ChatService
from packages.chat.request import ChatRequest
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
        system_prompt: str,
        tool_manager: ToolManager,
    ) -> None:

        self._chat = chat_service
        self._builder = prompt_builder
        self._system_prompt = system_prompt
        self._tools = tool_manager

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        prompt = self._builder.build(
            system_prompt=self._system_prompt,
            memories=state["memories"],
            context=state["context"],
            messages=state["messages"],
        )

        request = ChatRequest(
            conversation_id=state["conversation_id"],
            messages=prompt,
            tools=self._tools.list() if state.get("tools_enabled", True) else [],
        )

        response = await self._chat.chat(request)

        response.message.content = normalize_message_content(response.message.content)

        state["messages"].append(response.message)

        return state