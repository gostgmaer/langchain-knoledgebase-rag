# Conversation summarizer
from __future__ import annotations

from langchain_core.messages import BaseMessage

from packages.chat.chat_service import ChatService


class ConversationSummarizer:
    """Summarizes long conversations."""

    def __init__(
        self,
        chat: ChatService,
    ) -> None:
        self.chat = chat

    async def summarize(
        self,
        messages: list[BaseMessage],
    ) -> str:
        prompt = """
Summarize the following conversation.

Requirements:
- Preserve important facts
- Preserve user preferences
- Preserve unresolved questions
- Remove repetitive content
- Keep under 500 words

Conversation:
"""

        response = await self.chat.chat(
            [
                *messages,
                {"role": "user", "content": prompt},
            ]
        )

        return response.content