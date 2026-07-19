# Empty file
from __future__ import annotations

import datetime
from uuid import UUID

from aiohttp import request

from packages.application.dto.conversation import (
    ConversationResponse,
    CreateConversationRequest,
)
from packages.application.exceptions import ResourceNotFoundError
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.models.conversation import Conversation
from packages.infrastructure.repositories.unit_of_work import UnitOfWork


class ConversationService:

    def __init__(
        self,
        uow: UnitOfWork,
    ) -> None:
        self._uow = uow

    async def get(
        self,
        conversation_id: UUID,
    ) -> ConversationResponse:
        """
        Retrieve a conversation by its ID.

        Raises:
            ResourceNotFoundError:
                If the conversation does not exist.
        """

        conversation = await self._uow.conversations.get(
            conversation_id,
        )

        if conversation is None:
            raise ResourceNotFoundError(f"Conversation '{conversation_id}' not found.")

        return ConversationResponse.model_validate(
            conversation,
        )

    async def get_or_create(
        self,
        request: CreateConversationRequest,
    ) -> ConversationResponse:

        conversation = await self.get_by_session(
            request.session_id,
        )

        if conversation is not None:
            return conversation

        return await self.create(
            request,
        )

    async def get_by_session(
        self,
        session_id: str,
    ) -> ConversationResponse | None:

        conversation = await self._uow.conversations.get_by_session_id(
            session_id,
        )

        if conversation is None:
            return None

        return ConversationResponse.model_validate(
            conversation,
        )

    async def create(
        self,
        request: CreateConversationRequest,
    ) -> ConversationResponse:

        conversation = Conversation(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            title=request.title,
        )

        conversation = await self._uow.conversations.create(
            conversation,
        )

        await self._uow.commit()

        return ConversationResponse.model_validate(
            conversation,
        )

    async def close(
        self,
        conversation_id: UUID,
    ) -> ConversationResponse:

        conversation = await self._uow.conversations.get(
            conversation_id,
        )

        if conversation is None:
            raise ResourceNotFoundError(f"Conversation '{conversation_id}' not found.")

        conversation.status = ConversationStatus.COMPLETED

        conversation.ended_at = datetime.utcnow()

        conversation = await self._uow.conversations.update(
            conversation,
        )

        await self._uow.commit()

        return ConversationResponse.model_validate(
            conversation,
        )

conversation: ConversationService = ConversationService