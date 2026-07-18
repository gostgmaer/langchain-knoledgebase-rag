# API lifespan
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.infrastructure.container import ApplicationContainer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI application lifecycle.

    Responsible for:

    - Building the dependency injection container
    - Initializing infrastructure
    - Running startup checks
    - Cleaning up resources on shutdown
    """

    #
    # Build dependency container
    #
    container = ApplicationContainer()

    #
    # Store container on app state
    #
    app.state.container = container

    #
    # Resolve core services
    #
    settings = container.settings.settings()
    logger = container.settings.logger()

    logger.info("Starting EasyDev AI Platform...")

    #
    # Initialize database
    #
    database = container.database.session_manager()

    await database.initialize()

    logger.info("Database initialized.")

    #
    # Initialize graph
    #
    graph = container.graph.manager()

    await graph.initialize()

    logger.info("LangGraph initialized.")

    #
    # Register tools
    #
    tools = container.tools.manager()

    await tools.initialize()

    logger.info("Tools initialized.")

    logger.info("Application startup completed.")

    try:
        yield

    finally:
        logger.info("Shutting down EasyDev AI Platform...")

        await database.close()

        logger.info("Database closed.")