from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequestSchema(BaseModel):
    """
    Incoming chat request.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    conversation_id: UUID = Field(
        description="Conversation identifier.",
    )

    message: str = Field(
        min_length=1,
        max_length=10000,
        description="User message.",
    )

    stream: bool = False


class ChatResponseSchema(BaseModel):
    """
    Chat response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    conversation_id: UUID

    response: str

    model: str

    usage: dict[str, int] = Field(default_factory=dict)