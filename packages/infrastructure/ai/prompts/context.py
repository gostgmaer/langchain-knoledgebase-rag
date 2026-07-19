from __future__ import annotations

from dataclasses import dataclass

from packages.domain.models.agent import Agent
from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message


@dataclass(slots=True)
class PromptContext:
    conversation: Conversation
    user_message: Message

    agent: Agent | None = None

    history: list[Message] | None = None

    memories: list[str] | None = None

    documents: list[str] | None = None

    tools: list[str] | None = None