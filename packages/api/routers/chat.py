# Router chat
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.chat import (
    ChatRequestSchema,
    ChatResponseSchema,
)
from packages.application.dto.chat import ChatRequest
from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_conversation,
    ensure_default_model_profile,
)
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ChatResponseSchema],
    summary="Chat with the AI assistant",
    description="Send a message to the conversation graph.",
)
async def chat(
    payload: ChatRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    """
    Execute a chat request.
    """

    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    conversations = container.repositories.conversation()

    if payload.conversation_id is not None:
        conversation = await conversations.get(payload.conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
    else:
        model_profiles = container.repositories.model_profile()
        agents = container.repositories.agent()
        profile = await ensure_default_model_profile(model_profiles)
        agent = await ensure_default_agent(tenant_id, profile.id, agents)
        conversation = await ensure_default_conversation(
            tenant_id,
            user_id,
            agent.id,
            conversations,
        )

    agents = container.repositories.agent()
    agent = await agents.get(conversation.agent_id)

    chat_service = container.chat_service.chat_service()

    response = await chat_service.chat(
        ChatRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=conversation.agent_id,
            session_id=conversation.session_id,
            conversation_id=conversation.id,
            message=payload.message,
            stream=payload.stream,
        )
    )

    return ApiResponse(
        message="Chat completed successfully.",
        data=ChatResponseSchema(
            conversation_id=response.conversation_id,
            response=response.response,
            model=agent.llm_model,
        ),
    )
