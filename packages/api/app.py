from __future__ import annotations

from fastapi import FastAPI

from packages.api.exception_handlers import register_exception_handlers
from packages.api.lifespan import lifespan
from packages.api.middleware import register_middlewares
from packages.api.routers import register_routers


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    app = FastAPI(
        title="EasyDev AI Platform",
        description="Production AI Platform powered by LangGraph",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    register_middlewares(app)
    register_exception_handlers(app)
    register_routers(app)

    return app


app = create_application()