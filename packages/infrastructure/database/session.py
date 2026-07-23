from __future__ import annotations

import contextvars

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


# Holds the current request/job's session so every repository resolved
# during it shares one transaction. A ContextVar (rather than mutating
# a provider override on the shared, process-wide ApplicationContainer)
# is what makes this safe under concurrency: asyncio isolates a
# ContextVar's value per-Task, so two requests or worker jobs running
# concurrently in the same event loop each see only their own bound
# session, never each other's — a container-level `.override()` is
# mutable state shared by every task in the process and one task's
# override stomping another's is exactly what caused a real
# `IllegalStateChangeError` under concurrent load (a session getting
# close()'d by its own request while another task's repositories were
# still using it, having been resolved after that request clobbered
# the shared override).
current_session: contextvars.ContextVar[AsyncSession | None] = contextvars.ContextVar(
    "current_session", default=None
)


def resolve_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncSession:
    """
    Returns the session bound to the current task via `current_session`,
    if one is set, otherwise creates a fresh one. Caller is responsible
    for closing whichever it gets back.
    """
    bound = current_session.get()
    if bound is not None:
        return bound
    return session_factory()