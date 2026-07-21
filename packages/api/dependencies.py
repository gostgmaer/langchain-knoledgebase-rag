# API dependencies
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from dependency_injector import providers
from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Request, status

from packages.infrastructure.ai.manager import LLMManager
from packages.conversation.manager import ConversationManager
from packages.graph.manager import GraphManager
from packages.infrastructure.container import ApplicationContainer
from packages.memory.manager import MemoryManager
from packages.sdk.iam.models import CurrentUser
from packages.tools.manager import ToolManager
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: dependency-injector's wiring does not see markers inside
# Annotated[...] metadata — keep Depends(Provide[...]) as a default value.


#
# Root Container
#


@inject
async def get_container(
    container: ApplicationContainer = Depends(Provide[ApplicationContainer]),
) -> ApplicationContainer:
    return container


@inject
async def get_db_session(
    session: AsyncSession = Depends(Provide[ApplicationContainer.database.session]),
):
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def request_scoped_session(
    container: ApplicationContainer,
) -> AsyncIterator[AsyncSession]:
    """
    Opens one session for the lifetime of a single request and overrides
    the whole DI tree onto it, so every repository/memory-store construction
    reached from this request shares one session instead of each opening
    its own (which either leaks a connection or breaks shared-transaction
    consistency across repos touched in the same request).

    Commits once at the end of a successful request, rolls back on
    exception. Repositories (packages/infrastructure/repositories/base.py)
    only flush(), never commit() — that's correct for them, since several
    repository calls in one request should share one transaction; this is
    the actual transaction boundary.
    """
    session = container.database.session()
    container.database.session.override(providers.Object(session))
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        container.database.session.reset_override()
        await session.close()


@inject
async def get_scoped_container(
    container: ApplicationContainer = Depends(Provide[ApplicationContainer]),
) -> AsyncIterator[ApplicationContainer]:
    async with request_scoped_session(container):
        yield container


#
# Well-known, fixed IDs used only as a fallback when a caller doesn't
# send X-Tenant-ID/X-User-ID, so the API is testable (curl, cli.py, the
# API docs "Try it out" button) without hand-generating UUIDs first.
# Real callers should still send their own — these are never invented
# silently for a header that's present but malformed.
#
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000002")


def require_uuid_header(
    request: Request,
    header: str,
    default: UUID | None = None,
) -> UUID:
    raw = request.headers.get(header)
    if not raw:
        if default is not None:
            return default
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{header} header is required.",
        )
    try:
        return UUID(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{header} must be a valid UUID.",
        )


#
# IAM
#
# The current user is resolved by AuthenticationMiddleware (see
# packages/api/middleware/authentication.py) and stashed on
# request.state — it fails open, so current_user is None whenever no
# token was presented or IAM rejected/couldn't be reached. Permission
# checks below mirror that: they only enforce once a real, verified
# user is present.
#


async def get_current_user(
    request: Request,
) -> CurrentUser | None:
    return getattr(request.state, "current_user", None)


def require_permission(code: str):
    """
    FastAPI dependency factory: raises 403 if a verified current user
    lacks the given permission code. No-ops (fail-open) when there's
    no verified user at all, matching AuthenticationMiddleware's
    fail-open design — enforcement only turns on once real auth flows.
    """

    async def _check(
        current_user: CurrentUser | None = Depends(get_current_user),
    ) -> None:
        if current_user is None:
            return

        if not any(
            permission.code == code
            for permission in current_user.permissions
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {code}",
            )

    return _check


def require_role(code: str):
    """Same as require_permission, checked against roles instead."""

    async def _check(
        current_user: CurrentUser | None = Depends(get_current_user),
    ) -> None:
        if current_user is None:
            return

        if not any(
            role.code == code
            for role in current_user.roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required role: {code}",
            )

    return _check


#
# AI
#


@inject
async def get_ai_manager(
    manager: LLMManager = Depends(Provide[ApplicationContainer.ai.manager]),
) -> LLMManager:
    return manager


#
# Conversation
#


@inject
async def get_conversation_manager(
    container: ApplicationContainer = Depends(Provide[ApplicationContainer]),
) -> AsyncIterator[ConversationManager]:
    async with request_scoped_session(container):
        yield container.conversation.manager()


#
# Graph
#


@inject
async def get_graph_manager(
    manager: GraphManager = Depends(Provide[ApplicationContainer.graph.manager]),
) -> GraphManager:
    return manager


#
# Memory
#


@inject
async def get_memory_manager(
    manager: MemoryManager = Depends(Provide[ApplicationContainer.memory.manager]),
) -> MemoryManager:
    return manager


#
# Tools
#


@inject
async def get_tool_manager(
    manager: ToolManager = Depends(Provide[ApplicationContainer.tools.manager]),
) -> ToolManager:
    return manager
