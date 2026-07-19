# Conversation formatter
from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from packages.domain.models.message import Message


class MessageFormatter:
    """Converts database messages into LangChain messages."""

    ROLE_MAP = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
    }

    def to_langchain(
        self,
        messages: list[Message],
    ) -> list[BaseMessage]:

        result: list[BaseMessage] = []

        for message in messages:
            role_val = message.role.value if hasattr(message.role, "value") else str(message.role)
            cls = self.ROLE_MAP.get(
                role_val.lower(),
                HumanMessage,
            )

            result.append(
                cls(content=message.content)
            )

        return result

    def system_prompt(
        self,
        prompt: str,
    ) -> SystemMessage:
        return SystemMessage(
            content=prompt,
        )