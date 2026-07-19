from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from packages.infrastructure.ai.models import LLMProvider


@dataclass(slots=True)
class RuntimeRequest:
    """Input for the AI runtime."""

    messages: list[BaseMessage]


@dataclass(slots=True)
class RuntimeResponse:
    """Output from the AI runtime."""

    provider: LLMProvider

    message: AIMessage

    model: str | None = None

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    finish_reason: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
