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

            # id must be stable across reloads and match the DB row —
            # LangGraph's checkpointer merges GraphState.messages via
            # add_messages, which matches by .id to decide "update
            # existing" vs "append new". Without this, every reload
            # produces fresh random ids (BaseMessage's default), so the
            # checkpointer never recognizes these as the same messages
            # it already has for this thread and appends them as
            # duplicates on every single turn — the conversation history
            # sent to the LLM silently doubles (then triples, ...) turn
            # over turn.
            result.append(
                cls(content=message.content, id=str(message.id))
            )

        return result

    def system_prompt(
        self,
        prompt: str,
    ) -> SystemMessage:
        return SystemMessage(
            content=prompt,
        )