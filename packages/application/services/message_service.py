from typing import Any
from uuid import UUID

from packages.domain.enums.message_role import MessageRole
from packages.domain.models.ai_response import AIResponse
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
        provider: str | None = None,
        model: str | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> Message:

        message = await self._create(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
        )

        # Raw provider snapshot, separate from the display-facing
        # Message row above — see packages/domain/models/ai_response.py.
        # Only recorded when there's real metadata to store; a provider
        # that returns an empty response_metadata/additional_kwargs
        # (or a code path that never threaded raw_response through at
        # all) just skips this rather than writing an empty row.
        if raw_response and (raw_response.get("response_metadata") or raw_response.get("additional_kwargs")):
            await self._uow.ai_responses.create(
                AIResponse(
                    message_id=message.id,
                    provider=provider or "unknown",
                    model=model or "unknown",
                    raw_response=raw_response,
                )
            )

        return message

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
