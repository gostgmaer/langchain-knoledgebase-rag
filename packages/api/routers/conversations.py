# Router conversations
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    conversation_visible_to,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.conversation import (
    MessageSourceSchema,
    ConversationCreateSchema,
    ConversationHistoryResponseSchema,
    ConversationResponseSchema,
    MessageResponseSchema,
)
from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_model_profile,
)
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.models.conversation import Conversation
from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.message_citation import MessageCitation
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


@router.get(
    "/{conversation_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ConversationResponseSchema],
    summary="Fetch a conversation",
    description="Fetches a single conversation's metadata by ID.",
)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    conversations = container.repositories.conversation()

    conversation = await conversations.get(conversation_id)

    if conversation is None or not conversation_visible_to(
        conversation, tenant_id, getattr(request.state, "current_user", None)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return ApiResponse(
        message="Conversation retrieved.",
        data=ConversationResponseSchema.model_validate(conversation),
    )


async def _with_sources(container: ApplicationContainer, history) -> list[MessageResponseSchema]:
    """Messages plus the customer-visible sources (label, document, page, section) of each answer."""
    ids = [m.id for m in history]
    by_message: dict[UUID, list[MessageSourceSchema]] = {}

    if ids:
        rows = (
            await container.database.session().execute(
                select(
                    MessageCitation.message_id,
                    MessageCitation.rank,
                    func.coalesce(MessageCitation.document_name, Document.file_name),
                    func.coalesce(MessageCitation.page_number, DocumentChunk.page_number),
                    func.coalesce(MessageCitation.section, DocumentChunk.section),
                )
                .join(Document, Document.id == MessageCitation.document_id, isouter=True)
                .join(DocumentChunk, DocumentChunk.id == MessageCitation.chunk_id, isouter=True)
                .where(MessageCitation.message_id.in_(ids))
                .order_by(MessageCitation.rank)
            )
        ).all()
        for message_id, rank, name, page, section in rows:
            by_message.setdefault(message_id, []).append(
                MessageSourceSchema(label=f"[{rank}]", document_name=name, page_number=page, section=section)
            )

    out = []
    for message in history:
        schema = MessageResponseSchema.model_validate(message)
        schema.sources = by_message.get(message.id, [])
        out.append(schema)
    return out


@router.get(
    "/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ConversationHistoryResponseSchema],
    summary="Fetch a conversation's message history",
    description=(
        "Closes Session Management's Conversation History gap — messages "
        "were always persisted, but had no HTTP-reachable read path until "
        "this route. Returns a page of messages oldest-first, matching the "
        "order they're fed into the LLM as context.\n\n"
        "A conversation_id that doesn't exist yet is auto-created (empty) "
        "under that exact ID rather than 404ing — mirrors POST /chat's own "
        "auto-create-under-given-ID behavior, since a client is expected to "
        "generate this ID itself and check its history before ever sending "
        "a first message."
    ),
)
async def get_conversation_history(
    conversation_id: UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    conversations = container.repositories.conversation()
    messages = container.repositories.message()

    conversation = await conversations.get(conversation_id)

    # An existing conversation that belongs to another tenant still 404s —
    # distinguishing "doesn't exist" from "exists but isn't yours" would
    # leak whether a given conversation_id is real to a caller who doesn't
    # own it, and auto-creating under an ID someone else already has isn't
    # possible anyway.
    if conversation is not None and not conversation_visible_to(
        conversation, tenant_id, getattr(request.state, "current_user", None)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    if conversation is None:
        model_profiles = container.repositories.model_profile()
        agents = container.repositories.agent()

        profile = await ensure_default_model_profile(model_profiles)
        agent = await ensure_default_agent(tenant_id, profile.id, agents)

        conversation = await conversations.create(
            Conversation(
                id=conversation_id,
                tenant_id=tenant_id,
                agent_id=agent.id,
                user_id=user_id,
                session_id=f"client-{conversation_id}",
                title="New conversation",
                status=ConversationStatus.ACTIVE,
            )
        )

    total = await messages.count_by_conversation(conversation_id)

    history = await messages.list_by_conversation(
        conversation_id,
        limit=limit,
        offset=offset,
    )

    return ApiResponse(
        message="Conversation history retrieved.",
        data=ConversationHistoryResponseSchema(
            conversation_id=conversation_id,
            total=total,
            limit=limit,
            offset=offset,
            messages=await _with_sources(container, history),
        ),
    )
