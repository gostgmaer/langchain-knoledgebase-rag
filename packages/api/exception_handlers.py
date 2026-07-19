# API exception handlers
from __future__ import annotations

from docx import settings
from fastapi import FastAPI, Request, logger
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import traceback
from starlette.exceptions import HTTPException

from packages.config.loader import settings
from packages.api.responses import ErrorResponse
from packages.logging.logger import get_logger

logger = get_logger(__name__)

async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="ValidationError",
            message="Request validation failed.",
            details={
                "errors": exc.errors(),
            },
        ).model_dump(mode="json"),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTPException",
            message=str(exc.detail),
        ).model_dump(mode="json"),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        exc_info=exc,
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )

    message = "An unexpected internal server error occurred."

    if settings.app.debug:
        message = traceback.format_exc()

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message=message,
        ).model_dump(mode="json"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.add_exception_handler(
        HTTPException,
        http_exception_handler,
    )

    app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )
