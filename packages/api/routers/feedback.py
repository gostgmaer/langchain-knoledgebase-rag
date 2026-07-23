# Router feedback
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.feedback import (
    FeedbackListResponseSchema,
    FeedbackResponseSchema,
    SubmitFeedbackRequestSchema,
)
from packages.domain.enums.feedback_rating import FeedbackRating
from packages.domain.models.feedback import Feedback
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[FeedbackResponseSchema],
    summary="Submit feedback on an assistant message",
    description=(
        "Records a thumbs-up/down (plus optional comment) on one assistant "
        "message. Resubmitting for the same message updates the existing "
        "feedback rather than creating a duplicate."
    ),
)
async def submit_feedback(
    payload: SubmitFeedbackRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    messages = container.repositories.message()
    conversations = container.repositories.conversation()
    feedback_repo = container.repositories.feedback()

    message = await messages.get(payload.message_id)
    conversation = await conversations.get(message.conversation_id) if message else None

    if message is None or conversation is None or conversation.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    existing = await feedback_repo.get_by_user_and_message(user_id, payload.message_id)

    if existing is not None:
        existing.rating = payload.rating
        existing.comment = payload.comment
        updated = await feedback_repo.update(existing)

        return ApiResponse(
            message="Feedback updated.",
            data=FeedbackResponseSchema.model_validate(updated),
        )

    feedback = Feedback(
        tenant_id=tenant_id,
        user_id=user_id,
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment,
    )

    created = await feedback_repo.create(feedback)

    return ApiResponse(
        message="Feedback submitted.",
        data=FeedbackResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[FeedbackListResponseSchema],
    summary="Review feedback",
    description="Lists the calling tenant's feedback, optionally filtered by rating, most recent first.",
)
async def list_feedback(
    request: Request,
    rating: FeedbackRating | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    feedback_repo = container.repositories.feedback()

    total = await feedback_repo.count_by_tenant(tenant_id, rating=rating)
    rows = await feedback_repo.list_by_tenant(tenant_id, rating=rating, limit=limit, offset=offset)

    return ApiResponse(
        message="Feedback retrieved.",
        data=FeedbackListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            feedback=[FeedbackResponseSchema.model_validate(f) for f in rows],
        ),
    )
