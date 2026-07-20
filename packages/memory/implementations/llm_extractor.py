"""
packages/memory/implementations/llm_extractor.py
"""

from __future__ import annotations

import json
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage

from packages.memory.extractor import MemoryExtractor
from packages.memory.schemas import (
    MemoryFact,
    MemoryType,
)


class LLMMemoryExtractor(MemoryExtractor):
    """
    LLM implementation of the MemoryExtractor.

    This class is responsible for extracting durable memories
    from a conversation using an LLM.
    """

    def __init__(
        self,
        llm: BaseChatModel,
    ) -> None:
        self._llm = llm

    async def extract(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> list[MemoryFact]:

        prompt = self._build_prompt(messages)

        response = await self._llm.ainvoke(
            [
                HumanMessage(content=prompt),
            ]
        )

        return self._parse_response(
            response.content,
            conversation_id,
            tenant_id,
            user_id,
        )

    # ---------------------------------------------------------
    # Prompt
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
You are an AI memory extraction system.

Your job is to extract ONLY durable information.

Remember:

✔ User preferences
✔ Long-term goals
✔ Skills
✔ Projects
✔ Personal profile
✔ Important recurring tasks

Ignore:

✘ Greetings
✘ Temporary requests
✘ Small talk
✘ Questions without lasting value

Return ONLY valid JSON.

Example:

[
  {{
    "type": "preference",
    "content": "User prefers PostgreSQL.",
    "importance": 0.95
  }}
]

Conversation:

{conversation}
"""

    # ---------------------------------------------------------
    # Response Parser
    # ---------------------------------------------------------

    def _parse_response(
        self,
        response: str,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> list[MemoryFact]:

        data = json.loads(response)

        memories: list[MemoryFact] = []

        for item in data:

            memories.append(
                MemoryFact(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    type=MemoryType(item["type"]),
                    content=item["content"],
                    importance=item.get(
                        "importance",
                        0.5,
                    ),
                )
            )

        return memories