"""
packages/prompts/builder.py
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from packages.memory.schemas import MemoryFact


class PromptBuilder:
    """
    Builds the complete prompt sent to the LLM, using a real
    ChatPromptTemplate (with a MessagesPlaceholder for conversation
    history) instead of hand-concatenated f-strings.
    """

    def build(
        self,
        *,
        system_prompt: str,
        memories: list[MemoryFact],
        context: list[str] | None,
        messages: list[BaseMessage],
    ) -> list[BaseMessage]:

        template_messages: list[tuple[str, str] | MessagesPlaceholder] = [
            ("system", "{system_prompt}"),
        ]
        variables: dict[str, Any] = {
            "system_prompt": system_prompt,
        }

        #
        # Long-Term Memory
        #

        if memories:
            template_messages.append(
                ("human", "Known facts about the user:\n\n{memory_text}")
            )
            variables["memory_text"] = "\n".join(
                f"- {memory.content}" for memory in memories
            )

        #
        # RAG Context
        #

        if context:
            template_messages.append(
                ("human", "Relevant knowledge:\n\n{context}")
            )
            variables["context"] = "\n\n".join(context)

        #
        # Conversation
        #

        template_messages.append(MessagesPlaceholder("conversation"))
        variables["conversation"] = messages

        template = ChatPromptTemplate.from_messages(template_messages)

        return template.invoke(variables).to_messages()
