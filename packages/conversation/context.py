# Conversation context
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from packages.conversation.formatter import MessageFormatter
from packages.conversation.history import ConversationHistory


class ConversationContextBuilder:
    """Builds the complete prompt context."""

    def __init__(
        self,
        history: ConversationHistory,
        formatter: MessageFormatter,
    ) -> None:
        self.history = history
        self.formatter = formatter

    async def build(
        self,
        *,
        conversation_id,
        system_prompt: str | None = None,
        documents: list[Document] | None = None,
        history_limit: int = 20,
    ) -> list[BaseMessage]:

        history = await self.history.load(
            conversation_id,
            limit=history_limit,
        )

        messages = self.formatter.to_langchain(
            history,
        )

        context: list[BaseMessage] = []
        
        context.extend(messages)

        return context