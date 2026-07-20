from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage
from sqlalchemy import UUID


@dataclass(slots=True)
class ChatRequest:
    """
    Represents a single chat request.
    """
    conversation_id: UUID
    messages: list[BaseMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    stream: bool = False
    tools: list[Any] = field(default_factory=list)
