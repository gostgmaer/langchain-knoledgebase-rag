"""
packages/memory/implementations/llm_extractor.py
"""

from __future__ import annotations

import re
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

Your job is to extract ONLY durable information about the USER —
their preferences, goals, skills, projects, profile, and recurring
tasks — from the conversation below.

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
✘ Anything the assistant (the "ai" turns below) said about ITSELF —
  its own capabilities, memory, architecture, whether it's stateless
  or session-based, what it can or cannot do, etc. These are never
  facts about the user, even when phrased confidently as if they
  were true. If the assistant was ever wrong about its own
  capabilities in an earlier turn, that mistake must NOT be captured
  here — it is not a durable fact, it is a bug in a different turn.

Return ONLY valid JSON. Each item's "type" MUST be exactly one of:
"fact", "preference", "profile", "task", "summary", "goal", "skill", "project" — no other values are accepted.
Every item's "content" must describe the USER, not the assistant.

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

# Defense-in-depth safety net, on top of the prompt instruction above —
# a real production incident (docs/ARCHITECTURE_TUTORIAL.md §13) showed
# the assistant's own wrong self-descriptions ("The AI operates on a
# session-based memory model...") getting extracted as durable facts,
# then re-poisoning every future conversation for that user regardless
# of which fixed the underlying prompt/reranking bugs that caused the
# wrong description in the first place. Matched against the start of
# the extracted *content* (how the extractor phrases a self-description
# it wrongly decided was worth keeping), not the raw conversation text —
# narrow on purpose, so a user's own statement that happens to mention
# "the AI" (e.g. "User wants the AI to reply in French") doesn't get
# misfiled as self-referential just for containing that phrase.
_SELF_REFERENTIAL_PATTERNS = [
    r"^\s*(?:the ai|this ai|the assistant|this assistant|the model|the chatbot)\b\s+(?:is|are|was|operates|does not|doesn't|cannot|can't|has|have|lacks)",
    r"^\s*i(?:'m| am)\s+(?:an ai|a language model|stateless|session-based)\b",
    r"^\s*as an ai\b",
    r"\bsession-based memory model\b",
    r"\bi don't have (?:persistent memory|any memory|access to (?:previous|prior|past) conversations)\b",
]

_SELF_REFERENTIAL_RE = re.compile(
    "|".join(_SELF_REFERENTIAL_PATTERNS),
    re.IGNORECASE,
)


def _is_self_referential(content: str) -> bool:
    return bool(_SELF_REFERENTIAL_RE.search(content))


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
                content = item["content"]

                if _is_self_referential(content):
                    logger.warning(
                        "Dropping self-referential memory extraction "
                        "(the assistant's own claim about itself, not "
                        "a fact about the user): %r",
                        content,
                    )
                    continue

                memories.append(
                    MemoryFact(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        type=MemoryType(item["type"]),
                        content=content,
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
