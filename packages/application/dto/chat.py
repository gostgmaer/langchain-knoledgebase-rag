# Empty file
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    tenant_id: UUID
    user_id: UUID
    agent_id: UUID
    session_id: str
    message: str = Field(
        min_length=1,
        max_length=100_000_0,
    )
    conversation_id: UUID | None = None
    stream: bool = False


class CitationDTO(BaseModel):
    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    score: float


class PendingToolCallDTO(BaseModel):
    id: str | None
    name: str | None
    args: dict


class PendingApprovalDTO(BaseModel):
    """
    Surfaced when packages/graph/nodes/tool.py's approval gate paused
    the graph — Phase 11 (Human in the Loop)'s approval workflow.
    """

    tool_calls: list[PendingToolCallDTO] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: UUID

    user_message_id: UUID | None = None

    assistant_message_id: UUID | None = None

    response: str = ""

    citations: list[CitationDTO] = Field(default_factory=list)

    pending_approval: PendingApprovalDTO | None = None