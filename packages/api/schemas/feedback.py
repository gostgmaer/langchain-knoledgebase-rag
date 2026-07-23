# Schema feedback
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.enums.feedback_rating import FeedbackRating


class SubmitFeedbackRequestSchema(BaseModel):
    """
    Incoming request to submit feedback on an assistant message.
    Resubmitting for the same message updates the existing feedback
    rather than creating a duplicate.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    message_id: UUID

    rating: FeedbackRating

    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponseSchema(BaseModel):
    """A single feedback record."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    tenant_id: UUID
    user_id: UUID
    message_id: UUID
    rating: str
    comment: str | None
    created_at: datetime


class FeedbackListResponseSchema(BaseModel):
    """A page of a tenant's feedback."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    feedback: list[FeedbackResponseSchema]
