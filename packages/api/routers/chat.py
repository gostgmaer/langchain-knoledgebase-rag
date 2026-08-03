# Router chat
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    request_scoped_session,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.chat import (
    ChatRequestSchema,
    ChatResponseSchema,
    ChatResumeRequestSchema,
    CitationSchema,
    PendingApprovalSchema,
    PendingToolCallSchema,
)
from packages.application.dto.chat import ChatRequest, ChatResponse
from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_conversation,
    ensure_default_model_profile,
)
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.models.conversation import Conversation
from packages.infrastructure.container import ApplicationContainer
from packages.shared.logging import get_logger

logger = get_logger(__name__)

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
    background_tasks: BackgroundTasks,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    """
    Execute a chat request.
    """

    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    conversations = container.repositories.conversation()

    conversation = (
        await conversations.get(payload.conversation_id)
        if payload.conversation_id is not None
        else None
    )

    if conversation is None:
        model_profiles = container.repositories.model_profile()
        agents = container.repositories.agent()
        profile = await ensure_default_model_profile(model_profiles)
        agent = await ensure_default_agent(tenant_id, profile.id, agents)

        if payload.conversation_id is not None:
            # An explicit conversation_id that doesn't exist yet gets
            # created under that exact ID, rather than 404ing — by
            # request, so a client-generated ID can be used as a
            # conversation handle from its very first message, without
            # a separate POST /conversations round-trip first.
            try:
                conversation = await conversations.create(
                    Conversation(
                        id=payload.conversation_id,
                        tenant_id=tenant_id,
                        agent_id=agent.id,
                        user_id=user_id,
                        session_id=f"client-{payload.conversation_id}",
                        title="New conversation",
                        status=ConversationStatus.ACTIVE,
                    )
                )
            except IntegrityError:
                # A real race, confirmed live: two genuinely simultaneous
                # first-messages to the same not-yet-existing
                # conversation_id both reach this branch, and only one
                # INSERT wins — the other hits a real UniqueViolationError
                # on conversations' primary key rather than a 404-worthy
                # "doesn't exist." A failed flush leaves the session
                # unusable until rolled back; the row the losing request
                # just conflicted with is, by definition, already
                # committed (Postgres only raises the duplicate-key error
                # once the winner's transaction commits), so re-fetching
                # here is safe rather than racy again.
                await container.database.session().rollback()
                conversation = await conversations.get(payload.conversation_id)
                if conversation is None:
                    raise
        else:
            conversation = await ensure_default_conversation(
                tenant_id,
                user_id,
                agent.id,
                conversations,
            )

    agents = container.repositories.agent()
    agent = await agents.get(conversation.agent_id)

    chat_service = container.chat_service.chat_service()

    chat_request = ChatRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=conversation.agent_id,
        session_id=conversation.session_id,
        conversation_id=conversation.id,
        message=payload.message,
        stream=payload.stream,
    )

    if payload.stream:
        return StreamingResponse(
            _sse_events(
                chat_service,
                chat_request,
                conversation.id,
                background_tasks,
                container,
                tenant_id,
                user_id,
                agent.system_prompt,
            ),
            media_type="text/event-stream",
        )

    response = await chat_service.chat(chat_request)

    if response.pending_approval is None:
        # Memory extraction only makes sense once the turn actually
        # produced a real assistant reply — a paused-on-approval
        # response has no completed turn to summarize/extract facts
        # from yet (see resume() below, which schedules it instead).
        background_tasks.add_task(
            _extract_memory_in_background,
            container,
            response.conversation_id,
            tenant_id,
            user_id,
            agent.system_prompt,
        )

    return ApiResponse(
        message=(
            "Tool call approval required."
            if response.pending_approval is not None
            else "Chat completed successfully."
        ),
        data=_to_response_schema(response, agent.llm_model),
    )


@router.post(
    "/{conversation_id}/resume",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ChatResponseSchema],
    summary="Approve or reject a pending tool call",
    description=(
        "Resumes a conversation previously paused by the tool-approval "
        "gate (see POST /chat's response.pending_approval) — Phase 11 "
        "(Human in the Loop)'s approval workflow. Non-streaming only."
    ),
)
async def resume(
    conversation_id: UUID,
    payload: ChatResumeRequestSchema,
    request: Request,
    background_tasks: BackgroundTasks,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    conversations = container.repositories.conversation()
    conversation = await conversations.get(conversation_id)

    if conversation is None or conversation.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    agents = container.repositories.agent()
    agent = await agents.get(conversation.agent_id)

    chat_service = container.chat_service.chat_service()

    response = await chat_service.resume(conversation_id, payload.approved)

    if response.pending_approval is None:
        background_tasks.add_task(
            _extract_memory_in_background,
            container,
            response.conversation_id,
            tenant_id,
            user_id,
            agent.system_prompt,
        )

    return ApiResponse(
        message=(
            "Tool call approval required."
            if response.pending_approval is not None
            else "Chat completed successfully."
        ),
        data=_to_response_schema(response, agent.llm_model),
    )


def _to_response_schema(response: ChatResponse, model: str) -> ChatResponseSchema:
    return ChatResponseSchema(
        conversation_id=response.conversation_id,
        response=response.response,
        model=model,
        citations=[
            CitationSchema(
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                chunk_index=citation.chunk_index,
                score=citation.score,
            )
            for citation in response.citations
        ],
        pending_approval=(
            PendingApprovalSchema(
                tool_calls=[
                    PendingToolCallSchema(
                        id=call.id,
                        name=call.name,
                        args=call.args,
                    )
                    for call in response.pending_approval.tool_calls
                ]
            )
            if response.pending_approval is not None
            else None
        ),
    )


async def _sse_events(
    chat_service,
    chat_request: ChatRequest,
    conversation_id,
    background_tasks: BackgroundTasks,
    container: ApplicationContainer,
    tenant_id: UUID,
    user_id: UUID,
    system_prompt: str,
):
    """
    Formats each event from ChatService.stream() as a Server-Sent
    Event: "token" per chunk, "citations" once the full response has
    been assembled (docs/mvpRAG.md v1.2 — previously a documented gap,
    streaming never surfaced retrieval citations at all), then either
    a terminal "done" once the full response has been generated and
    persisted, or — if the tool-approval gate paused the graph
    mid-stream (see GraphManager.stream()'s own "interrupt" event) — a
    terminal "interrupt" event instead, with memory extraction skipped,
    the same way the non-streaming path skips it for a pending
    approval. Resuming a stream-paused conversation still goes through
    the non-streaming POST /chat/{conversation_id}/resume endpoint —
    resuming *as* a stream isn't supported, a deliberate, documented
    scope boundary, not a silent gap.
    """

    async for event in chat_service.stream(chat_request):
        if event["type"] == "interrupt":
            payload = {
                "type": "interrupt",
                "conversation_id": str(conversation_id),
                "tool_calls": event["tool_calls"],
            }
            yield f"data: {json.dumps(payload)}\n\n"
            return
        if event["type"] == "citations":
            yield f"data: {json.dumps({'type': 'citations', 'citations': event['citations']})}\n\n"
            continue
        yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"

    background_tasks.add_task(
        _extract_memory_in_background,
        container,
        conversation_id,
        tenant_id,
        user_id,
        system_prompt,
    )

    yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation_id)})}\n\n"


async def _extract_memory_in_background(
    container: ApplicationContainer,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    system_prompt: str,
) -> None:
    """
    Runs long-term memory extraction + conversation summarization
    after the response has already been sent — this used to be a
    graph node (`extract_memory`, between `llm` and END) that the
    request awaited synchronously, adding two full LLM calls to every
    single turn's latency for pure side-effect work with zero bearing
    on the reply the user already received.

    Opens its own fresh request-scoped session rather than reusing the
    original request's, for the same reason `_ingest_in_background`
    does in packages/api/routers/documents.py: this runs after the
    response is sent, by which point the original request's session
    may already be closed. Rebuilds the message history via
    `ConversationContextBuilder` (the same helper `ChatService` used to
    build the graph's input state) instead of threading LangChain
    message objects out of the graph — both the user's and the
    assistant's messages are already committed to the DB by the time
    this runs, so a fresh rebuild sees exactly what the graph saw.
    """

    try:
        async with request_scoped_session(container):
            context_builder = container.conversation.context()
            messages = await context_builder.build(
                conversation_id=conversation_id,
                system_prompt=system_prompt,
            )

            extract_memory = container.graph.extract_memory()
            await extract_memory(
                {
                    "conversation_id": conversation_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "messages": messages,
                }
            )

    except Exception as exc:
        logger.exception(
            "Background memory extraction failed",
            conversation_id=str(conversation_id),
            error=str(exc),
        )
