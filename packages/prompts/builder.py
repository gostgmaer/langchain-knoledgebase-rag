"""
packages/prompts/builder.py
"""

from __future__ import annotations

from typing import Any

import tiktoken
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from packages.config.loader import settings
from packages.memory.schemas import MemoryFact

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


class PromptBuilder:
    """
    Builds the complete prompt sent to the LLM, using a real
    ChatPromptTemplate (with a MessagesPlaceholder for conversation
    history) instead of hand-concatenated f-strings.
    """

    def _dedup_and_budget(self, context: list[str]) -> list[str]:
        """
        Drops exact-duplicate chunks (multi-query retrieval can surface
        the same chunk more than once) and truncates to a token budget
        so a large merged/reranked context can't blow out the prompt.
        """

        seen: set[str] = set()
        deduped: list[str] = []
        for chunk in context:
            if chunk in seen:
                continue
            seen.add(chunk)
            deduped.append(chunk)

        budget = settings.rag.context_token_budget
        budgeted: list[str] = []
        used = 0
        for chunk in deduped:
            tokens = len(_TOKENIZER.encode(chunk))
            if used + tokens > budget:
                break
            budgeted.append(chunk)
            used += tokens

        return budgeted

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
            budgeted_context = self._dedup_and_budget(context)
            if budgeted_context:
                template_messages.append(
                    ("human", "Relevant knowledge:\n\n{context}")
                )
                variables["context"] = "\n\n".join(budgeted_context)

        #
        # Conversation
        #

        template_messages.append(MessagesPlaceholder("conversation"))
        variables["conversation"] = messages

        template = ChatPromptTemplate.from_messages(template_messages)

        return template.invoke(variables).to_messages()
