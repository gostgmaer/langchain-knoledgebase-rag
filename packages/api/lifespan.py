from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from arq.connections import RedisSettings as ArqRedisSettings
from arq.connections import create_pool
from dependency_injector import providers
from fastapi import FastAPI

from packages.graph.visualizer import GraphVisualizer
from packages.infrastructure.container import ApplicationContainer
from packages.infrastructure.container.graph import create_postgres_checkpointer
from packages.infrastructure.database.base import Base
from sqlalchemy import text
import packages.domain.models  # noqa: F401 - Ensure models are loaded for Base.metadata
from packages.shared.logging import configure_logger, get_logger


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

    logger.info("Initializing database schema...")
    try:
        engine = container.database.engine()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc)
        raise

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
        # Rendering uses the remote mermaid.ink API — never block startup on it.
        builder = container.graph.builder()
        GraphVisualizer.save_png(builder.build())
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

        engine = container.database.engine()
        await engine.dispose()
        container.unwire()
        logger.info("Database engine disposed")
