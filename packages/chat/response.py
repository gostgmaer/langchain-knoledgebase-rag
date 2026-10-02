from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage


@dataclass(slots=True)
class LLMChatResponse:
    """
    `LLMChatService`'s response to one `LLMChatRequest`.
    """

    message: AIMessage

    usage: dict[str, Any] = field(default_factory=dict)

    provider: str = ""

    model: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)