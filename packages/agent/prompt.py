from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from packages.graph.state import GraphState


class PromptBuilder:
    """
    Builds the final prompt sent to the LLM.
    """

    def build(
        self,
        state: GraphState,
    ) -> list[BaseMessage]:

        messages = list(
            state["messages"],
        )

        system_messages: list[BaseMessage] = []

        system_content = []

        #
        # System prompt
        #
        system_prompt = state.get(
            "system_prompt",
        )

        if system_prompt:
            system_content.append(system_prompt)

        #
        # Retrieved RAG context
        #
        context = state.get(
            "context",
        )

        if context and context.text:
            system_content.append(f"Context:\n\n{context.text}")

        if system_content:
            system_messages.append(
                SystemMessage(
                    content="\n\n".join(system_content)
                )
            )

        return [
            *system_messages,
            *messages,
        ]