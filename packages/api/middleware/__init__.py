# Middleware init
from __future__ import annotations

from fastapi import FastAPI

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
    # Request ID (outermost)
    #
    app.add_middleware(
        RequestIdMiddleware,
    )