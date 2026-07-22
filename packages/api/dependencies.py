# API dependencies
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from dependency_injector import providers
from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Request, status

from packages.infrastructure.ai.manager import LLMManager
from packages.config.loader import settings
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
    FastAPI dependency factory: raises 401 if no verified user is
    present, 403 if they lack the given permission code. `roles`/
    `permissions` on `CurrentUser` are plain string codes (e.g.
    `"user:read"`), matching the real IAM service's JWT claim shape
    (`packages/sdk/iam/models.py`), not `{id, name, code}` objects.

    Gated behind `settings.features.enable_rbac` — a master kill-switch
    (`ENABLE_RBAC` in `.env`, default off). While off, this no-ops
    entirely regardless of whether a route uses it, so attaching
    `Depends(require_permission(...))` to a route today is inert until
    the flag flips on — deliberately, since the real IAM integration
    (`packages/sdk/iam/`) was only just corrected against the live
    service and hasn't been verified end-to-end with real credentials
    yet (see `docs/CHANGELOG.md`).
    """

    async def _check(
        current_user: CurrentUser | None = Depends(get_current_user),
    ) -> None:
        if not settings.features.enable_rbac:
            return

        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )

        if code not in current_user.permissions:
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
        if not settings.features.enable_rbac:
            return

        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )

        if code not in current_user.roles:
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
