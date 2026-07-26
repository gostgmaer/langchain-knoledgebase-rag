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

    conversation_id: UUID | None = Field(
        default=None,
        description=(
            "Conversation identifier. Omit to use (or auto-create) a "
            "default conversation for the calling tenant/user — useful "
            "for quick testing without calling POST /conversations first."
        ),
    )

    message: str = Field(
        min_length=1,
        max_length=10000,
        description="User message.",
    )

    stream: bool = False


class CitationSchema(BaseModel):
    """
    A single retrieved-chunk citation backing part of the response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    document_id: UUID

    chunk_id: UUID

    chunk_index: int

    score: float


class PendingToolCallSchema(BaseModel):
    """
    One tool call awaiting approval — see PendingApprovalSchema.
    """

    id: str | None
    name: str | None
    args: dict


class PendingApprovalSchema(BaseModel):
    """
    Present when packages/graph/nodes/tool.py's approval gate paused
    the graph instead of executing a tool call — Phase 11 (Human in
    the Loop)'s approval workflow. Resume via
    POST /chat/{conversation_id}/resume with {"approved": true/false}.
    """

    tool_calls: list[PendingToolCallSchema] = Field(default_factory=list)


class ChatResumeRequestSchema(BaseModel):
    """
    Approves or rejects tool call(s) a prior POST /chat response left
    pending (see ChatResponseSchema.pending_approval).
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    approved: bool = Field(
        description="True to run the pending tool call(s), False to reject them.",
    )


class ChatResponseSchema(BaseModel):
    """
    Chat response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    conversation_id: UUID

    response: str = ""

    model: str

    usage: dict[str, int] = Field(default_factory=dict)

    citations: list[CitationSchema] = Field(default_factory=list)

    pending_approval: PendingApprovalSchema | None = None