from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.api import dependencies
from packages.api.routers import chat, health
from packages.infrastructure.container import ApplicationContainer
from packages.shared.logging import configure_logger, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI application lifecycle.
    """

    container = ApplicationContainer()

    # Wire the container to the modules that use Provide(...)
    container.wire(
        packages=[
            dependencies,
            chat,
            health,
        ]
    )

    app.state.container = container

    settings = container.settings.config()

    configure_logger(settings.logging.level)

    logger = get_logger(__name__)

    logger.info("Starting EasyDev AI Platform")

    try:
        yield

    finally:
        logger.info("Shutting down EasyDev AI Platform")

        container.unwire()

        engine = container.database.engine()
        await engine.dispose()

        logger.info("Database engine disposed")
