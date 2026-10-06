# Schema widget — the public, unauthenticated embeddable chat widget (docs/BUGS.md item 37)
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WidgetConfigSchema(BaseModel):
    """What the embedded widget needs to render itself — nothing internal."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    greeting: str


class WidgetChatRequestSchema(BaseModel):
    """
    A message from an anonymous website visitor. `visitor_id` is generated and persisted by the
    widget's own JS (localStorage), not by this app — sending the same one back is what makes a
    visitor's conversation continue across page loads instead of starting over every message.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    visitor_id: UUID
    conversation_id: UUID | None = None


class WidgetCitationSchema(BaseModel):
    """A source backing part of the answer — public-safe fields only, no internal ids or scores."""

    model_config = ConfigDict(from_attributes=True)

    label: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    section: str | None = None
    source_name: str | None = None
    url: str | None = None
    updated_at: datetime | None = None


class WidgetChatResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID
    message: str
    citations: list[WidgetCitationSchema] = Field(default_factory=list)
