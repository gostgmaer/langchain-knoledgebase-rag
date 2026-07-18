# Agent response
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage


@dataclass(slots=True)
class AgentUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class AgentResponse:
    """
    Standard response returned by AgentRuntime.
    """

    message: AIMessage

    model: str

    usage: AgentUsage = field(default_factory=AgentUsage)

    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    finish_reason: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)