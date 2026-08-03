from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from dependency_injector import providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from packages.infrastructure.container import ApplicationContainer
from packages.infrastructure.database.session import current_session


class _RBACDisabledFeatureFlagService:
    """
    Deterministic stand-in for FeatureFlagService in API tests.

    The real service (packages/infrastructure/container/feature_flags.py)
    is wired directly onto `database.session_factory` — a raw, un-
    overridden `async_sessionmaker` — not `database.session`, so it always
    talks to the real, live dev database and is unaffected by the
    `client` fixture's transaction-rollback override. That means any
    route gated by `require_role`/`require_permission` would depend on
    whatever `enable_rbac`'s real, currently-committed value happens to
    be (confirmed live: it's `False` right now, but this session's own
    manual verification work flipped it `True` earlier — genuinely
    mutable external state a test suite shouldn't depend on). This fake
    keeps RBAC deterministically off for every API test, matching the
    documented default.
    """

    async def get_effective(self, key: str, tenant_id) -> bool:
        return False

    def invalidate(self, key: str, tenant_id=None) -> None:
        pass


@pytest_asyncio.fixture
async def container() -> AsyncIterator[ApplicationContainer]:
    """
    One real ApplicationContainer per test, wired against this dev
    environment's actual .env (the same Postgres/Redis this session has
    been manually verifying against all day) — not a mock, matching
    every other verification done this session. Constructing it wires
    `packages.api` (see packages/api/lifespan.py's own comment on this),
    which is enough for `Depends(Provide[...])`-style injection to work
    in route handlers without running the full app lifespan (checkpointer/
    OTel/job-queue startup) that individual tests don't need.

    Function-scoped, not session-scoped, on purpose: pytest-asyncio
    hands each test function its own event loop by default, and a
    SQLAlchemy async engine's connection pool is bound to whichever
    loop was running when it was first resolved — sharing one engine
    (and its asyncpg connections) across tests running on different
    event loops raises `RuntimeError: Event loop is closed` at
    teardown, confirmed live while building this fixture. A fresh
    container (and therefore a fresh, correctly-loop-bound engine) per
    test avoids that entirely, at the cost of a new connection pool
    per test — fine at this suite's size.
    """
    app_container = ApplicationContainer()
    try:
        yield app_container
    finally:
        engine = app_container.database.engine()
        await engine.dispose()
        app_container.unwire()


@pytest_asyncio.fixture
async def db_session(container: ApplicationContainer) -> AsyncIterator[AsyncSession]:
    """
    One real transaction against the live dev Postgres per test, rolled
    back unconditionally at teardown — including anything the code under
    test itself commits. `join_transaction_mode="create_savepoint"` makes
    an inner `session.commit()` (e.g. packages/api/dependencies.py's
    request_scoped_session, which every repository call goes through)
    release a SAVEPOINT instead of a real COMMIT, so the rollback below
    still discards everything.

    Bound onto the same `current_session` ContextVar the app itself reads
    (packages/infrastructure/database/session.py's `resolve_session`), so
    any repository/service resolved through `container` during the test
    transparently shares this one session instead of opening its own.
    """
    engine = container.database.engine()
    connection = await engine.connect()
    trans = await connection.begin()
    session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")

    token = current_session.set(session)
    try:
        yield session
    finally:
        current_session.reset(token)
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(container: ApplicationContainer) -> AsyncIterator[AsyncClient]:
    """
    An async HTTP client driving the real FastAPI app in-process via
    `ASGITransport` — deliberately not Starlette's synchronous
    `TestClient`, which runs the ASGI app in a separate thread/event
    loop via its own portal. That would hand the raw asyncpg connection
    opened below to a *different* event loop than the one that created
    it, which asyncpg/SQLAlchemy don't support. `ASGITransport` runs the
    whole request on this same test's event loop instead.

    Every request through this client shares one rolled-back transaction
    (same savepoint technique as `db_session` above), via a Factory
    override on `container.database.session` bound to one held-open
    connection — a Factory rather than a fixed session object because
    `request_scoped_session` closes the session it resolves at the end
    of every request, so a single fixed session object wouldn't survive
    a test that makes more than one request.

    Does not run the app's real `lifespan()` — that also stands up the
    Postgres checkpointer, OpenTelemetry, and the arq job queue, none of
    which the route tests below exercise, and `lifespan()` is already
    covered by every live manual/uvicorn run done this session.
    """
    from packages.api.app import app

    engine = container.database.engine()
    connection = await engine.connect()
    trans = await connection.begin()

    def _make_session() -> AsyncSession:
        return AsyncSession(bind=connection, join_transaction_mode="create_savepoint")

    container.database.session.override(providers.Factory(_make_session))
    container.feature_flags.service.override(providers.Object(_RBACDisabledFeatureFlagService()))
    app.state.container = container

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    finally:
        container.database.session.reset_override()
        container.feature_flags.service.reset_override()
        await trans.rollback()
        await connection.close()
