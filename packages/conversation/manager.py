# Conversation manager



from __future__ import annotations
from __future__ import annotations

from uuid import UUID

from packages.chat.chat_service import ChatService
from packages.conversation.models import (
    ChatRequest,
    ChatResponse,
)
from packages.conversation.service import ConversationService


class ConversationManager:
    """Coordinates chat, history and persistence."""

    def __init__(
        self,
        service: ConversationService,
        chat: ChatService,
    ) -> None:
        self.service = service
        self.chat = chat

    async def chat_completion(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        conversation = await self.service.get(
            request.conversation_id
        )

        if conversation is None:
            raise ValueError("Conversation not found.")

        response = await self.chat.chat(
            request.message
        )

        return ChatResponse(
            conversation_id=request.conversation_id,
            response=response.content,
            model=response.response_metadata.get(
                "model_name",
                "",
            ),
            usage=response.usage_metadata or {},
        )

    async def history(
        self,
        conversation_id: UUID,
    ):
        return await self.service.list_messages(
            conversation_id
        )