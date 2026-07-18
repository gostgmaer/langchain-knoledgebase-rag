from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.graph.visualizer import GraphVisualizer
from packages.infrastructure.container import ApplicationContainer
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

    try:
        # Rendering uses the remote mermaid.ink API — never block startup on it.
        GraphVisualizer.save_png(container.graph.builder().build())
    except Exception as exc:
        logger.warning("Could not render graph.png: %s", exc)

    try:
        yield

    finally:
        logger.info("Shutting down EasyDev AI Platform")

        container.unwire()

        engine = container.database.engine()
        await engine.dispose()

        logger.info("Database engine disposed")
