# Router conversations
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.conversation import (
    ConversationCreateSchema,
    ConversationResponseSchema,
)
from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_model_profile,
)
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.models.conversation import Conversation
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ConversationResponseSchema],
    summary="Start a new conversation",
    description=(
        "Creates a conversation for the calling tenant/user against a "
        "default agent, auto-provisioning that default agent (and the "
        "default model profile it references) on first use."
    ),
)
async def create_conversation(
    payload: ConversationCreateSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    model_profiles = container.repositories.model_profile()
    agents = container.repositories.agent()
    conversations = container.repositories.conversation()

    profile = await ensure_default_model_profile(model_profiles)
    agent = await ensure_default_agent(tenant_id, profile.id, agents)

    conversation = Conversation(
        tenant_id=tenant_id,
        agent_id=agent.id,
        user_id=user_id,
        session_id=str(uuid4()),
        title=payload.title,
        status=ConversationStatus.ACTIVE,
    )

    created = await conversations.create(conversation)

    return ApiResponse(
        message="Conversation created.",
        data=ConversationResponseSchema.model_validate(created),
    )
