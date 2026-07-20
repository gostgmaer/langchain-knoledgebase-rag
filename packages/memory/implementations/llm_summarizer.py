"""
packages/memory/implementations/llm_summarizer.py
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from packages.infrastructure.ai.manager import LLMManager
from packages.memory.schemas import (
    MemoryFact,
    MemoryType,
)
from packages.memory.summarizer import MemorySummarizer

_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an AI conversation summarizer.

Summarize the conversation into a concise paragraph.

The summary should preserve:

- User goals
- Decisions
- Important context
- Current work
- Unfinished tasks

Do NOT include:

- Greetings
- Small talk
- Repeated information""",
        ),
        ("human", "Conversation:\n\n{conversation}"),
    ]
)


class LLMMemorySummarizer(MemorySummarizer):
    """
    LLM implementation of the MemorySummarizer.

    Generates a concise summary of a conversation that can be
    stored as long-term conversational context.
    """

    def __init__(
        self,
        llm: LLMManager,
    ) -> None:
        self._chain = _SUMMARY_PROMPT | llm.model

    async def summarize(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> MemoryFact:

        conversation = "\n".join(
            f"{m.type}: {m.content}"
            for m in messages
        )

        response = await self._chain.ainvoke({"conversation": conversation})

        return MemoryFact(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            type=MemoryType.SUMMARY,
            content=response.text.strip(),
            importance=1.0,
        )
