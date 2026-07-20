"""
packages/memory/implementations/llm_extractor.py
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from packages.infrastructure.ai.manager import LLMManager
from packages.memory.extractor import MemoryExtractor
from packages.memory.implementations.output_parser import MemoryFactListParser
from packages.memory.schemas import (
    MemoryFact,
    MemoryType,
)
from packages.shared.logging import get_logger

logger = get_logger(__name__)

_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an AI memory extraction system.

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

Return ONLY valid JSON. Each item's "type" MUST be exactly one of:
"fact", "preference", "profile", "task", "summary", "goal", "skill", "project" — no other values are accepted.

Example:

[
  {{
    "type": "preference",
    "content": "User prefers PostgreSQL.",
    "importance": 0.95
  }},
  {{
    "type": "project",
    "content": "User is building a startup called Acme Robotics.",
    "importance": 0.9
  }}
]""",
        ),
        ("human", "Conversation:\n\n{conversation}"),
    ]
)


class LLMMemoryExtractor(MemoryExtractor):
    """
    LLM implementation of the MemoryExtractor.

    This class is responsible for extracting durable memories
    from a conversation using an LLM.
    """

    def __init__(
        self,
        llm: LLMManager,
    ) -> None:
        self._chain = _EXTRACTION_PROMPT | llm.model | MemoryFactListParser()

    async def extract(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> list[MemoryFact]:

        conversation = "\n".join(
            f"{m.type}: {m.content}"
            for m in messages
        )

        try:
            data = await self._chain.ainvoke({"conversation": conversation})
        except OutputParserException as exc:
            logger.warning(
                "Memory extraction returned non-JSON output, skipping this turn: %s",
                exc,
            )
            return []

        memories: list[MemoryFact] = []

        for item in data:

            try:
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
            except (KeyError, ValueError):
                logger.warning(
                    "Skipping malformed memory extraction item: %r", item
                )

        return memories
