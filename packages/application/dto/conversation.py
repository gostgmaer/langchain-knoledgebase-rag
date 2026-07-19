from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from packages.domain.enums.conversation_status import ConversationStatus


class CreateConversationRequest(BaseModel):
    tenant_id: UUID
    user_id: UUID
    agent_id: UUID
    session_id: str
    title: str | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    tenant_id: UUID
    user_id: UUID
    agent_id: UUID

    session_id: str

    title: str | None
    summary: str | None

    status: ConversationStatus

    total_messages: int
    total_tokens: int
    total_cost: float

    started_at: datetime
    last_message_at: datetime | None
    ended_at: datetime | None