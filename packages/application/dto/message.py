# Empty file
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from packages.domain.enums.message_role import MessageRole


class CreateMessageRequest(BaseModel):
    conversation_id: UUID
    role: MessageRole
    content: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str