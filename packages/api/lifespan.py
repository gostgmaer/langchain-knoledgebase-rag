from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from arq.connections import RedisSettings as ArqRedisSettings
from arq.connections import create_pool
from dependency_injector import providers
from fastapi import FastAPI
from sqlalchemy import text

import packages.domain.models  # noqa: F401 - Ensure models are loaded for Base.metadata
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.infrastructure.database.upgrades import apply_schema_upgrades
from packages.graph.visualizer import GraphVisualizer
from packages.infrastructure.container import ApplicationContainer
from packages.infrastructure.container.graph import create_postgres_checkpointer
from packages.infrastructure.database.base import Base
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.shared.logging import configure_logger, get_logger
from packages.shared.tracing import configure_opentelemetry
from packages.api.middleware.rate_limit import close_rate_limit_redis
from packages.memory.manager import close_memory_lock_redis
from packages.tools.builtin.weather import close_weather_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI application lifecycle.
    """

    # Instantiating the container wires "packages.api" via wiring_config.
    container = ApplicationContainer()

    app.state.container = container

    settings = container.settings.config()

    configure_logger(settings.logging.level)

    logger = get_logger(__name__)

    logger.info("Starting EasyDev AI Platform")

    if settings.observability.active:
        logger.info(
            "LangSmith tracing enabled",
            project=settings.observability.project,
        )
    else:
        logger.info("LangSmith tracing disabled (no LANGCHAIN_API_KEY or LANGCHAIN_TRACING_V2=false)")

    # Non-fatal, same idiom as the checkpointer/queue-pool setup below —
    # an unreachable OTLP collector degrades to "no tracing" rather
    # than blocking startup.
    if configure_opentelemetry(app, settings.observability):
        logger.info(
            "OpenTelemetry tracing enabled",
            endpoint=settings.observability.otel_endpoint,
        )
    else:
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED=false or setup failed)")

    logger.info("Initializing database schema...")
    try:
        engine = container.database.engine()
        async with engine.begin() as conn:
            if settings.database.schema_init_at_startup:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.run_sync(Base.metadata.create_all)
                await apply_schema_upgrades(conn)
            else:
                logger.info("SCHEMA_INIT_AT_STARTUP=false: not touching the schema; run alembic upgrade head.")
            bypass = (
                await conn.execute(
                    text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).scalar_one_or_none()
            if bypass:
                logger.warning(
                    "Row-level security is NOT enforced: the database role is a superuser or has "
                    "BYPASSRLS. Query-layer tenant filters still apply; connect as an ordinary role "
                    "in production (docs/PROVENANCE.md, scripts/create_app_role.sql)."
                )
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc)
        raise

    # Seeds the one genuinely global default this app owns outright: the
    # default ModelProfile (packages/conversation/bootstrap.py), idempotent
    # (get-or-create) so this is a no-op after the first boot. Agent,
    # Conversation and KnowledgeBase defaults are deliberately NOT seeded
    # here — all three require a tenant_id, and tenants are owned by the
    # external IAM system (docs/PROVENANCE.md), not a local table this app
    # can enumerate at startup. They stay lazily created on first per-tenant
    # use (packages/api/routers/chat.py, conversations.py, documents.py).
    try:
        async with container.database.session_factory()() as session:
            await ensure_default_model_profile(ModelProfileRepository(session))
            await session.commit()
        logger.info("Default model profile ready.")
    except Exception as exc:
        logger.warning("Could not seed the default model profile: %s", exc)

    # Writes one row per known Platform Setting (packages/application/services/
    # platform_settings_service.py's SETTINGS) with its built-in default, for
    # every key that doesn't have a row yet — so the platform_settings table
    # is never empty on first boot. Idempotent: only fills in missing keys,
    # never touches one an admin already overrode.
    try:
        await container.platform_settings.service().seed_defaults()
        logger.info("Platform settings seeded with built-in defaults.")
    except Exception as exc:
        logger.warning("Could not seed default platform settings: %s", exc)

    # Persistent (Postgres-backed) checkpointing — Session Management's
    # "Persistent Sessions" gap. Deliberately non-fatal: the in-memory
    # MemorySaver default (packages/infrastructure/container/graph.py)
    # already keeps the app fully functional, so a checkpointer-specific
    # connection issue degrades checkpointing rather than blocking
    # startup, the same "never block startup" idiom as the graph.png
    # render below.
    checkpointer_conn = None
    try:
        checkpointer = await create_postgres_checkpointer()
        checkpointer_conn = checkpointer.conn
        container.graph.checkpointer.override(providers.Object(checkpointer))
        logger.info("Persistent (Postgres-backed) checkpointer ready.")
    except Exception as exc:
        logger.warning(
            "Could not set up persistent checkpointer, falling back to in-memory: %s",
            exc,
        )

    try:
        # Rendering uses the remote mermaid.ink API — never block startup
        # on it. That comment was only half-true before: save_png() is a
        # synchronous call with no timeout of its own, made directly on
        # the event loop, so a slow/hanging mermaid.ink response (not
        # just a fast connection-refused) blocked startup indefinitely —
        # confirmed live, the health check never went healthy while this
        # sat waiting. asyncio.to_thread + wait_for gives it a real,
        # enforced ceiling so the "never block startup" intent is
        # actually true now, not just documented.
        builder = container.graph.builder()
        await asyncio.wait_for(
            asyncio.to_thread(GraphVisualizer.save_png, builder.build()),
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Could not render graph.png: %s", exc)

    # Producer-side pool for enqueuing jobs onto the real arq queue
    # (packages/worker/) — e.g. document ingestion, see
    # packages/api/routers/documents.py. Same non-fatal idiom as the
    # checkpointer above: document.py falls back to running ingestion
    # in-process via BackgroundTasks when this stays None.
    queue_pool = None
    try:
        queue_pool = await create_pool(ArqRedisSettings.from_dsn(settings.redis.url))
        container.queue.pool.override(providers.Object(queue_pool))
        logger.info("Job queue ready — document ingestion will enqueue onto arq.")
    except Exception as exc:
        logger.warning(
            "Could not connect to Redis for the job queue, falling back to "
            "in-process ingestion: %s",
            exc,
        )

    try:
        yield

    finally:
        logger.info("Shutting down EasyDev AI Platform")

        if checkpointer_conn is not None:
            # A plain sync psycopg connection now (ThreadedPostgresSaver,
            # packages/infrastructure/container/graph.py) — .close() is a
            # blocking call, run off the event loop like every other call
            # through this checkpointer.
            await asyncio.to_thread(checkpointer_conn.close)
        container.graph.checkpointer.reset_override()

        if queue_pool is not None:
            await queue_pool.aclose()
        container.queue.pool.reset_override()

        # packages/tools/builtin/weather.py's client is module-level and
        # never recreated per-request — production-readiness gap #1,
        # a leaked connector/socket on every shutdown until now.
        await close_weather_client()

        # Same idiom, same reason — RateLimitMiddleware's Redis client (docs/BUGS.md item 2).
        await close_rate_limit_redis()

        # Same idiom, same reason — MemoryManager's distributed summarize() lock (docs/BUGS.md item 2).
        await close_memory_lock_redis()

        engine = container.database.engine()
        await engine.dispose()
        container.unwire()
        logger.info("Database engine disposed")
