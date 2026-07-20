"""
packages/memory/implementations/llm_summarizer.py
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage

from packages.memory.schemas import (
    MemoryFact,
    MemoryType,
)
from packages.memory.summarizer import MemorySummarizer
from packages.shared.messages import normalize_message_content


class LLMMemorySummarizer(MemorySummarizer):
    """
    LLM implementation of the MemorySummarizer.

    Generates a concise summary of a conversation that can be
    stored as long-term conversational context.
    """

    def __init__(
        self,
        llm: BaseChatModel,
    ) -> None:
        self._llm = llm

    async def summarize(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> MemoryFact:

        prompt = self._build_prompt(messages)

        response = await self._llm.ainvoke(
            [
                HumanMessage(content=prompt),
            ]
        )

        return MemoryFact(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            type=MemoryType.SUMMARY,
            content=normalize_message_content(response.content).strip(),
            importance=1.0,
        )

    # ---------------------------------------------------------

    def _build_prompt(
        self,
        messages: list[BaseMessage],
    ) -> str:

        conversation = "\n".join(
            f"{m.type}: {m.content}"
            for m in messages
        )

        return f"""
You are an AI conversation summarizer.

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
- Repeated information

Conversation:

{conversation}
"""