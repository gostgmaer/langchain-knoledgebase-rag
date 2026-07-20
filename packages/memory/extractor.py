"""
packages/memory/extractor.py

AI Memory Extractor

Extracts durable memories from conversations.

The extractor is responsible for identifying information that
should be remembered long-term, such as:

- User preferences
- User profile
- Long-running tasks
- Important facts

The implementation may use an LLM, rules, or a hybrid approach.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from uuid import UUID

from langchain_core.messages import BaseMessage

from packages.memory.schemas import MemoryFact


class MemoryExtractor(ABC):
    """Extracts long-term memories from conversations."""

    @abstractmethod
    async def extract(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> list[MemoryFact]:
        """
        Extract durable memories from a conversation.

        Returns:
            A list of extracted MemoryFact objects.
        """
        ...