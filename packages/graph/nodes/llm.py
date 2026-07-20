"""
packages/graph/nodes/llm.py
"""

from __future__ import annotations

from packages.graph.state import GraphState
from packages.prompts.builder import PromptBuilder
from packages.application.services.chat_service import ChatService


class LLMNode:
    """
    Executes the LLM.

    Responsibilities:
    - Build the prompt
    - Invoke the LLM
    - Update the graph state

    This node does not know how prompts are constructed.
    """

    def __init__(
        self,
        chat_service: ChatService,
        prompt_builder: PromptBuilder,
        system_prompt: str,
    ) -> None:

        self._chat = chat_service
        self._builder = prompt_builder
        self._system_prompt = system_prompt

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

        response = await self._chat.ainvoke(
            messages=prompt,
        )

        state["messages"].append(response)

        return state