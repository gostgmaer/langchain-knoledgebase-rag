# Conversation models
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class ConversationContext:
    """Conversation context passed to the LLM."""

    conversation_id: UUID
    user_id: UUID | None = None
    system_prompt: str | None = None
    history: list[Any] = field(default_factory=list)
    documents: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatRequest:
    """Incoming chat request."""

    conversation_id: UUID
    message: str

    user_id: UUID | None = None

    system_prompt: str | None = None

    stream: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    """LLM response."""
    conversation_id: UUID
    response: str
    model: str
    stream: bool = False
    usage: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)