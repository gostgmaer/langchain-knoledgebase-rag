from __future__ import annotations

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
