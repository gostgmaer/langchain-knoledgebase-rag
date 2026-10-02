from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatFiltersSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_types: list[str] | None = Field(default=None, max_length=20)
    categories: list[str] | None = Field(default=None, max_length=20)
    tags: list[str] | None = Field(default=None, max_length=20)
    language: str | None = Field(default=None, max_length=20)
    sources: list[str] | None = Field(default=None, max_length=20, description="Only these source types.")
    source_ids: list[UUID] | None = Field(default=None, max_length=50, description="Only these knowledge sources.")


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

    filters: "ChatFiltersSchema | None" = Field(
        default=None,
        description="Restrict retrieval to documents with this metadata (applied inside the search).",
    )


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

    label: str | None = None
    """Marker to cite in the answer text, e.g. \"[1]\"."""

    document_name: str | None = None

    page_number: int | None = None

    section: str | None = None

    source_type: str | None = None
    """Where the document came from: upload, web, confluence, ..."""

    source_name: str | None = None

    url: str | None = None
    """The original page/file URL for external sources (never an internal API URL)."""

    updated_at: datetime | None = None
    """When the source last changed the document."""


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