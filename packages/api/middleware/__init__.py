# Middleware init
from __future__ import annotations

from fastapi import FastAPI

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