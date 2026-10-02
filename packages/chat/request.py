from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage
from sqlalchemy import UUID

from packages.infrastructure.ai.config import LLMConfig


@dataclass(slots=True)
class LLMChatRequest:
    """
    A single request to `LLMChatService` — send these messages to the configured LLM.
    """
    conversation_id: UUID
    messages: list[BaseMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    stream: bool = False
    tools: list[Any] = field(default_factory=list)
    # Set when the conversation's agent has a non-default ModelProfile whose
    # provider LLMChatService can actually serve (packages/graph/nodes/llm.py
    # resolves it) — docs/BUGS.md item 15: ModelProfile.provider/.model used
    # to be stored but never read; the global default was silently used
    # regardless. None means "use the shared default LLMManager", same as
    # before this field existed.
    llm_config: LLMConfig | None = None
