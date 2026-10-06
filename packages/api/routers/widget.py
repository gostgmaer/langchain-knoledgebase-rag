# Router widget — the public, unauthenticated embeddable chat widget (docs/BUGS.md item 37)
"""
Everything here is reachable from the open internet with no IAM token and no X-Tenant-ID/X-User-ID
header — this is the actual trust boundary for this feature, not the admin console. Two layers
keep it safe:

1. `widget_public_id` finds the agent, but `widget_allowed_origins` decides whether the request is
   answered at all — an empty list (the default) means nobody can use the widget yet, not that
   everybody can. CORS headers are only ever set for a validated origin, never echoed blindly.
2. `set_widget_mode(True)` restricts the agent's own tool access for the duration of the request
   (packages/tools/context.py) — an anonymous visitor gets knowledge-base search and the
   calculator, never the IAM lookup tools or a tenant's CUSTOM webhook tools.

Non-streaming only, and the response is trimmed to public-safe fields (packages/api/schemas/
widget.py) — no internal ids, scores, or anything the full authenticated /chat response includes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from packages.api.dependencies import get_scoped_container
from packages.api.middleware.rate_limit import is_rate_limited
from packages.api.responses import ApiResponse
from packages.api.schemas.widget import (
    WidgetChatRequestSchema,
    WidgetChatResponseSchema,
    WidgetCitationSchema,
    WidgetConfigSchema,
)
from packages.application.dto.chat import ChatRequest
from packages.conversation.bootstrap import ensure_default_conversation
from packages.domain.models.agent import Agent
from packages.infrastructure.container import ApplicationContainer
from packages.shared.access import set_retrieval_filters
from packages.tools.context import set_widget_mode

router = APIRouter(prefix="/widget", tags=["Widget"])

MAX_MESSAGES_PER_MINUTE = 20


async def _agent_for(public_id: str, container: ApplicationContainer) -> Agent:
    agent = await container.repositories.agent().get_by_widget_public_id(public_id)
    if agent is None or not agent.widget_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    return agent


def _allowed_origin(agent: Agent, request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin and origin in (agent.widget_allowed_origins or []):
        return origin
    return None


def _require_origin(agent: Agent, request: Request, response: Response) -> None:
    """Sets CORS headers for a validated origin, or raises 403 — call before doing any work."""
    origin = _allowed_origin(agent, request)
    if origin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This site is not allowed to use this widget.",
        )
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"


@router.options("/{public_id}/config", include_in_schema=False)
@router.options("/{public_id}/chat", include_in_schema=False)
async def preflight(
    public_id: str,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    # A disabled/unknown widget, or a disallowed origin, still gets a plain 204 (no CORS headers)
    # rather than an error — the browser's own CORS enforcement then blocks the real request, and
    # an OPTIONS response body is never visible to page JS anyway, so there is nothing to leak.
    agent = await container.repositories.agent().get_by_widget_public_id(public_id)
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    origin = _allowed_origin(agent, request) if agent is not None and agent.widget_enabled else None
    if origin:
        out.headers["Access-Control-Allow-Origin"] = origin
        out.headers["Vary"] = "Origin"
        out.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        out.headers["Access-Control-Allow-Headers"] = "Content-Type"
        out.headers["Access-Control-Max-Age"] = "600"
    return out


@router.get(
    "/{public_id}/config",
    response_model=ApiResponse[WidgetConfigSchema],
    summary="Widget display config",
    description="What the embedded widget needs to render itself. Requires an allowed Origin header.",
)
async def get_config(
    public_id: str,
    request: Request,
    response: Response,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    agent = await _agent_for(public_id, container)
    _require_origin(agent, request, response)

    return ApiResponse(
        message="Widget config retrieved.",
        data=WidgetConfigSchema(
            name=agent.name,
            greeting=agent.description or f"Hi! Ask me anything about {agent.name}.",
        ),
    )


@router.post(
    "/{public_id}/chat",
    response_model=ApiResponse[WidgetChatResponseSchema],
    summary="Send a message as an anonymous website visitor",
    description=(
        "Non-streaming. Restricted tool access (see module docstring) and a public-safe response "
        "shape — no internal ids, scores, or anything beyond what a website visitor should see."
    ),
)
async def chat(
    public_id: str,
    payload: WidgetChatRequestSchema,
    request: Request,
    response: Response,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    agent = await _agent_for(public_id, container)
    _require_origin(agent, request, response)

    client_ip = request.client.host if request.client else "unknown"
    if await is_rate_limited("widget", f"{public_id}:{client_ip}", MAX_MESSAGES_PER_MINUTE):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages. Please wait a moment and try again.",
        )

    set_widget_mode(True)
    set_retrieval_filters(None)

    conversations = container.repositories.conversation()
    if payload.conversation_id is not None:
        conversation = await conversations.get(payload.conversation_id)
        if (
            conversation is None
            or conversation.tenant_id != agent.tenant_id
            or conversation.user_id != payload.visitor_id
        ):
            conversation = None
    else:
        conversation = None
    if conversation is None:
        conversation = await ensure_default_conversation(
            agent.tenant_id, payload.visitor_id, agent.id, conversations,
        )

    chat_request = ChatRequest(
        tenant_id=agent.tenant_id,
        user_id=payload.visitor_id,
        agent_id=agent.id,
        session_id=conversation.session_id,
        conversation_id=conversation.id,
        message=payload.message,
        stream=False,
    )

    chat_service = container.chat_service.chat_service()
    result = await chat_service.chat(chat_request)

    if result.pending_approval is not None:
        # The restricted widget toolset (knowledge-base search, calculator) never triggers the
        # human-in-the-loop approval gate in practice, but an anonymous visitor has no way to
        # approve one if some future tool ever did — answer gracefully rather than expose the
        # approval machinery or crash.
        text = "Sorry, I can't complete that right now — could you rephrase your question?"
    else:
        text = result.response

    return ApiResponse(
        message="Message sent.",
        data=WidgetChatResponseSchema(
            conversation_id=result.conversation_id,
            message=text,
            citations=[WidgetCitationSchema.model_validate(c) for c in result.citations],
        ),
    )
