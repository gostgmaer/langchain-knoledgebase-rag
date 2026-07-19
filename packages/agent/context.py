from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from packages.rag.schemas import Citation
from packages.rag.schemas import Context


@dataclass(slots=True)
class AgentContext:
    """
    Context available during agent execution.
    """

    context: Context | None = None

    citations: list[Citation] | None = None

    summary: str | None = None

    tenant_id: UUID | None = None

    user_id: UUID | None = None

    conversation_id: UUID | None = None