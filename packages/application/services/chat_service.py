import datetime

from packages import conversation
from packages.application.dto.chat import ChatRequest, ChatResponse
from packages.application.dto.conversation import CreateConversationRequest
from packages.application.dto.message import CreateMessageRequest
from packages.application.services.conversation_service import (
    ConversationService,
)
from packages.application.services.message_service import (
    MessageService,
)

from packages.domain.enums.message_role import MessageRole
from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message
from packages.infrastructure.repositories.unit_of_work import (
    UnitOfWork,
)


class ChatService:

    def __init__(
        self,
        uow: UnitOfWork,
        conversation_service: ConversationService,
        message_service: MessageService,
    ) -> None:

        self._uow = uow
        self._conversation_service = conversation_service
        self._message_service = message_service

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        try:
            conversation = await self._get_conversation(request)

            user_message = await self._save_user_message(
                conversation,
                request,
            )

            assistant_response = await self._execute_runtime(
                conversation,
                user_message,
            )

            assistant_message = await self._save_assistant_message(
                conversation,
                assistant_response,
            )

            await self._update_conversation(conversation)

            await self._uow.commit()

            return ChatResponse(
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response=assistant_response,
            )

        except Exception:
            await self._uow.rollback()
            raise

    async def _get_conversation(
        self,
        request: ChatRequest,
    ) -> Conversation:
        return await self._conversation_service.get_or_create(
            CreateConversationRequest(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                agent_id=request.agent_id,
                session_id=request.session_id,
            )
        )

    async def _save_user_message(
        self,
        conversation: Conversation,
        request: ChatRequest,
    ) -> Message:
        return await self._message_service.create_user_message(
            conversation_id=conversation.id,
            content=request.message,
        )

    async def _execute_runtime(
        self,
        conversation: Conversation,
        message: Message,
    ) -> str:
        return "Hello! AI Runtime is not connected yet."

    async def _save_assistant_message(
        self,
        conversation: Conversation,
        response: str,
    ) -> Message:
        return await self._message_service.create_assistant_message(
            conversation_id=conversation.id,
            content=response,
        )

    async def _update_conversation(
        self,
        conversation: Conversation,
    ) -> None:
        await self._conversation_service.touch(
            conversation,
        )

    async def touch(
        self,
        conversation: Conversation,
    ) -> None:
        conversation.total_messages += 2
        conversation.last_message_at = datetime.now(datetime.UTC)

        await self._uow.conversations.update(
            conversation,
        )
