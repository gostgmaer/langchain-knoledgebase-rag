# Router chat
from __future__ import annotations

from dependency_injector.wiring import inject
from fastapi import APIRouter, status

from packages.api.dependencies import get_conversation_manager
from packages.api.responses import ApiResponse
from packages.api.schemas.chat import (
    ChatRequestSchema,
    ChatResponseSchema,
)
from packages.conversation.manager import ConversationManager
from packages.conversation.models import ChatRequest

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
@inject
async def chat(
    request: ChatRequestSchema,
    manager: ConversationManager = get_conversation_manager(),
) -> ApiResponse[ChatResponseSchema]:
    """
    Execute a chat request.
    """

    response = await manager.chat(
        ChatRequest(
            conversation_id=request.conversation_id,
            message=request.message,
            stream=request.stream,
        )
    )

    return ApiResponse(
        message="Chat completed successfully.",
        data=ChatResponseSchema.model_validate(
            response,
        ),
    )
