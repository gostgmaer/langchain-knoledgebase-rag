from __future__ import annotations

from fastapi import FastAPI

from packages.api.exception_handlers import register_exception_handlers
from packages.api.lifespan import lifespan
from packages.api.middleware import register_middlewares
from packages.api.routers import register_routers
from packages.config.loader import settings


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    # Phase 1 (Foundation)'s own OpenAPI acceptance bar: docs gated
    # behind environment/debug settings, not always-on in production
    # (docs/mvpRAG.md v1.2 — previously a documented, unwired gap:
    # APISettings.docs_url/redoc_url/openapi_url existed but nothing
    # ever read them, so /docs, /redoc, and the raw schema were
    # unconditionally public regardless of APP_ENV/DEBUG). Gated on
    # APP_ENV specifically, not DEBUG — this dev environment's own
    # .env runs with DEBUG=False (it only controls whether tracebacks
    # leak into error responses, see exception_handlers.py) but still
    # expects /docs available locally; only a real "production"
    # environment should ever hide them.
    docs_enabled = settings.app.environment.lower() != "production"

    app = FastAPI(
        title="EasyDev AI Platform",
        description="Production AI Platform powered by LangGraph",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=settings.api.docs_url if docs_enabled else None,
        redoc_url=settings.api.redoc_url if docs_enabled else None,
        openapi_url=settings.api.openapi_url if docs_enabled else None,
    )

    register_middlewares(app)
    register_exception_handlers(app)
    register_routers(app)

    return app


app = create_application()