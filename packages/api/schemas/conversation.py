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


class MessageSourceSchema(BaseModel):
    """
    Customer-visible citation: which document (and where in it) backed an answer. Deliberately
    carries no internal ids, scores or retrieval details - those are admin-only
    (see /retrieval-logs).
    """

    label: str
    document_name: str | None = None
    page_number: int | None = None
    section: str | None = None
    source_type: str | None = None
    source_name: str | None = None
    url: str | None = None
    updated_at: datetime | None = None


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
    sources: list[MessageSourceSchema] = []


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
