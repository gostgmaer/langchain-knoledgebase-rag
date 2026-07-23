# Middleware init
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from packages.config.loader import settings

from .authentication import AuthenticationMiddleware
from .logging import LoggingMiddleware
from .request_id import RequestIdMiddleware
from .tenant import TenantMiddleware


def register_middlewares(app: FastAPI) -> None:
    """
    Register all application middlewares.

    NOTE:
    FastAPI/Starlette executes middleware in reverse order of
    registration, so register from innermost to outermost.
    """

    #
    # Authentication (innermost — runs last, right before the route,
    # so it can override TenantMiddleware's header-or-default fallback
    # with a genuinely IAM-verified identity when one is available)
    #
    app.add_middleware(
        AuthenticationMiddleware,
    )

    #
    # Business Middleware
    #
    app.add_middleware(
        TenantMiddleware,
    )

    #
    # Logging
    #
    app.add_middleware(
        LoggingMiddleware,
    )

    #
    # Request ID
    #
    app.add_middleware(
        RequestIdMiddleware,
    )

    #
    # CORS (outermost — must run first on the way in, to answer
    # preflight OPTIONS requests before TenantMiddleware/auth ever see
    # them). Explicit custom headers listed since browsers block
    # X-Tenant-ID/X-User-ID by default unless a CORS response allows
    # them by name. frontend/ (a separate Next.js origin in dev) is
    # the reason this exists at all — see packages/config/api.py.
    #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["X-Tenant-ID", "X-User-ID", "Content-Type", "Authorization"],
    )