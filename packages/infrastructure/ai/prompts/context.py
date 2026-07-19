from __future__ import annotations

from dataclasses import dataclass, field

from packages.domain.models.agent import Agent
from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message


@dataclass(slots=True)
class PromptContext:
    """
    Complete context used to build an LLM prompt.
    """

    conversation: Conversation

    user_message: Message

    history: list[Message] = field(default_factory=list)

    memories: list[str] = field(default_factory=list)

    documents: list[str] = field(default_factory=list)

    system_prompt: str | None = None

    agent: Agent | None = None