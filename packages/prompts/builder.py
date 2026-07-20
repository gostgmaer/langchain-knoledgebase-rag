"""
packages/prompts/builder.py
"""

from __future__ import annotations

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from packages.memory.schemas import MemoryFact


class PromptBuilder:
    """
    Builds the complete prompt sent to the LLM.
    """

    def build(
        self,
        *,
        system_prompt: str,
        memories: list[MemoryFact],
        context: str | None,
        messages: list[BaseMessage],
    ) -> list[BaseMessage]:

        prompt: list[BaseMessage] = []

        #
        # System Prompt
        #

        prompt.append(
            SystemMessage(
                content=system_prompt,
            )
        )

        #
        # Long-Term Memory
        #

        if memories:

            memory_text = "\n".join(f"- {memory.content}" for memory in memories)

            prompt.append(HumanMessage(content=f"""
Known facts about the user:

{memory_text}
"""))

        #
        # RAG Context
        #

        if context:

            prompt.append(HumanMessage(content=f"""
Relevant knowledge:

{context}
"""))

        #
        # Conversation
        #

        prompt.extend(messages)

        return prompt
