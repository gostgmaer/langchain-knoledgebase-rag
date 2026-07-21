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

        # Memory/context are folded into the single system message, not
        # appended as separate "human" turns — as separate human messages
        # they read to the model as things the *user* just typed, which
        # caused real live confusion (a retrieved chunk got treated as
        # "information you have provided", and empty-context turns had no
        # signal that retrieval ran at all vs. never happened).
        sections = [system_prompt]

        if memories:
            memory_text = "\n".join(f"- {memory.content}" for memory in memories)
            sections.append(
                "Known facts about the user, from long-term memory "
                f"(not written by the user in this message):\n\n{memory_text}"
            )

        if context is not None:
            budgeted_context = self._dedup_and_budget(context) if context else []
            if budgeted_context:
                context_text = "\n\n".join(budgeted_context)
                sections.append(
                    "Relevant knowledge retrieved from the knowledge base for "
                    "this specific question (not written by the user — this is "
                    "retrieval output, use it to answer if relevant):\n\n"
                    f"{context_text}"
                )
            else:
                sections.append(
                    "The knowledge base was searched for this specific question "
                    "and no matching documents were found. Say so plainly if "
                    "relevant — do not claim you have no knowledge base at all, "
                    "and do not invent a public/web search you did not perform."
                )

        variables: dict[str, Any] = {
            "system_prompt": "\n\n---\n\n".join(sections),
            "conversation": messages,
        }

        template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder("conversation"),
            ]
        )

        return template.invoke(variables).to_messages()
