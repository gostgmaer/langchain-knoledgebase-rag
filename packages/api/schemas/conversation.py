from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreateSchema(BaseModel):
    """
    Incoming request to start a new conversation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    title: str | None = Field(
        default=None,
        max_length=255,
        description="Optional conversation title.",
    )


class ConversationResponseSchema(BaseModel):
    """
    A created conversation.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    agent_id: UUID
    user_id: UUID
    title: str | None
    status: str


class MessageResponseSchema(BaseModel):
    """
    A single message within a conversation's history.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    role: str
    content: str
    status: str
    created_at: datetime


class ConversationHistoryResponseSchema(BaseModel):
    """
    A page of a conversation's message history, oldest first.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    conversation_id: UUID
    total: int
    limit: int
    offset: int
    messages: list[MessageResponseSchema]
