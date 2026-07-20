"""
packages/memory/summarizer.py

AI Memory Summarizer

Responsible for generating conversation summaries that can be
used as long-term conversational context.

The summarizer does not persist summaries. It only generates them.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from uuid import UUID

from langchain_core.messages import BaseMessage

from packages.memory.schemas import MemoryFact


class MemorySummarizer(ABC):
    """
    Generates conversation summaries for long-term memory.
    """

    @abstractmethod
    async def summarize(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> MemoryFact:
        """
        Generate a summary for a conversation.

        Returns:
            MemoryFact of type SUMMARY.
        """
        ...