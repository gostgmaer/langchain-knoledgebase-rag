from uuid import UUID

from packages.domain.enums.message_role import MessageRole
from packages.domain.models.message import Message
from packages.infrastructure.database.transaction import UnitOfWork
from packages.application.dto.message import CreateMessageRequest

class MessageService:

    def __init__(
        self,
        uow: UnitOfWork,
    ) -> None:
        self._uow = uow

    async def _create(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        return await self._uow.messages.create(
            message,
        )

    async def create_user_message(
        self,
        conversation_id: UUID,
        content: str,
    ) -> Message:

        return await self._create(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
        )

    async def create_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
    ) -> Message:

        return await self._create(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
        )

    async def create_tool_message(
        self,
        conversation_id: UUID,
        content: str,
    ) -> Message:

        return await self._create(
            conversation_id=conversation_id,
            role=MessageRole.TOOL,
            content=content,
        )

    async def create_system_message(
        self,
        conversation_id: UUID,
        content: str,
    ) -> Message:

        return await self._create(
            conversation_id=conversation_id,
            role=MessageRole.SYSTEM,
            content=content,
        )
