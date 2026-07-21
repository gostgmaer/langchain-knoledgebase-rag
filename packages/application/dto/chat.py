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


class ChatResponse(BaseModel):
    conversation_id: UUID

    user_message_id: UUID

    assistant_message_id: UUID

    response: str

    citations: list[CitationDTO] = Field(default_factory=list)