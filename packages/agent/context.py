# Agent context
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document


@dataclass(slots=True)
class AgentContext:

    documents: list[Document]

    summary: str | None

    tenant_id: str | None

    user_id: str | None

    conversation_id: str | None