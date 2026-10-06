# API exception handlers
from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from packages.api.responses import ErrorResponse
from packages.config.loader import settings
from packages.logging.logger import get_logger

logger = get_logger(__name__)

def _json_safe_errors(errors: list[dict]) -> list[dict]:
    """
    `exc.errors()` puts the raw exception a custom pydantic `field_validator` raised in
    `ctx['error']` — useful for debugging, but that's a live Python object (a `ValueError`
    instance, not a string), and `model_dump(mode="json")` has no idea how to serialize one. Left
    as-is, this crashes the handler that exists specifically to turn a validation failure into a
    clean response, turning a 422 into an unhandled 500 instead — stringify it before it gets
    anywhere near JSON.
    """
    cleaned = []
    for err in errors:
        err = dict(err)
        ctx = err.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            err["ctx"] = {**ctx, "error": str(ctx["error"])}
        cleaned.append(err)
    return cleaned


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
                "errors": _json_safe_errors(exc.errors()),
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


def _is_provider_outage(exc: BaseException, seen: set[int] | None = None) -> bool:
    """LLM / embedding provider overloaded or unreachable (not a bug in this app)."""
    # One visited-set for the whole walk, including nested exception groups: a group and the exceptions it
    # contains can reference each other through __context__, which made this recurse until RecursionError
    # (masking the real error as a bare 500).
    seen = set() if seen is None else seen
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        # Exception groups (anyio task groups) wrap the real cause.
        for inner in getattr(exc, "exceptions", ()) or ():
            if _is_provider_outage(inner, seen):
                return True
        module = type(exc).__module__ or ""
        name = type(exc).__name__
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if module.startswith(("google.genai", "google.api_core", "openai", "anthropic", "groq")) and (
            name in {"ServerError", "ServiceUnavailable", "APIConnectionError", "APITimeoutError", "InternalServerError", "RateLimitError"}
            or status_code in (429, 500, 502, 503, 504)
        ):
            return True
        if name in {"CircuitBreakerOpenError", "CircuitOpenError"}:
            return True
        exc = exc.__cause__ or exc.__context__
    return False


async def provider_outage_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.warning(
        "AI provider unavailable",
        extra={"path": request.url.path, "method": request.method, "error": str(exc)[:200]},
    )
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "30"},
        content=ErrorResponse(
            error="ProviderUnavailable",
            message="The AI provider is temporarily unavailable or overloaded. Please try again in a moment.",
        ).model_dump(mode="json"),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if _is_provider_outage(exc):
        return await provider_outage_handler(request, exc)

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
