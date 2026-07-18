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

    messages: list[BaseMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_id: UUID
    stream: bool = False
