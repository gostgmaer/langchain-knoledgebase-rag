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

        #
        # System prompt
        #
        system_prompt = state.get(
            "system_prompt",
        )

        if system_prompt:
            system_messages.append(
                SystemMessage(
                    content=system_prompt,
                )
            )

        #
        # Retrieved RAG context
        #
        context = state.get(
            "context",
        )

        if context and context.text:
            system_messages.append(
                SystemMessage(
                    content=f"Context:\n\n{context.text}",
                )
            )

        return [
            *system_messages,
            *messages,
        ]