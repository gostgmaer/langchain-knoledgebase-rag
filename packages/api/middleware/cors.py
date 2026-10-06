# Middleware CORS
from __future__ import annotations

import functools
from collections.abc import Iterable, Sequence

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ALL_METHODS = ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT")
SAFELISTED_HEADERS = {"accept", "accept-language", "content-language", "content-type"}


class DynamicCORSMiddleware:
    """
    Pure ASGI, not `BaseHTTPMiddleware` — deliberately mirroring how Starlette's own
    `CORSMiddleware` is written, for the same reason: `BaseHTTPMiddleware` buffers a response to
    inspect it, which would break this app's SSE chat streaming (`POST /chat` with
    `stream: true`). A naive rewrite on top of `BaseHTTPMiddleware` would silently reintroduce
    that bug the first time someone tested a streaming request through it.

    Reads the allowed-origins list fresh (through `PlatformSettingsService`'s own ~30s
    in-process cache) on every request, instead of Starlette's `CORSMiddleware` building its
    matcher once from a list fixed at process startup — docs/BUGS.md item 38: an admin's change
    on the Platform Settings page takes effect without a restart.

    Exempts `exempt_prefix` entirely (the public embeddable chat widget,
    `packages/api/routers/widget.py`) — confirmed live, a genuine browser preflight to that
    router came back `400` from Starlette's `CORSMiddleware` intercepting it with this app's one
    static origin list, before the route's own per-agent, database-backed origin check ever ran.
    That router already answers its own preflight and sets its own per-request CORS headers;
    this middleware needs to just not be in its way, not merge policies with it.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        exempt_prefix: str,
        get_allowed_origins,
        allow_methods: Sequence[str] = ("GET",),
        allow_headers: Sequence[str] = (),
        allow_credentials: bool = False,
        max_age: int = 600,
    ) -> None:
        self.app = app
        self._exempt_prefix = exempt_prefix
        self._get_allowed_origins = get_allowed_origins
        """Async callable returning the current allowed-origins list — a thin wrapper around
        `PlatformSettingsService.get("cors_origins")`, injected rather than looked up from
        `scope["app"].state` here so this middleware stays independently testable."""
        self._allow_methods = ALL_METHODS if "*" in allow_methods else tuple(allow_methods)
        self._allow_headers_lower = sorted(SAFELISTED_HEADERS | {h.lower() for h in allow_headers})
        self._allow_headers_display = sorted(SAFELISTED_HEADERS | {h.lower() for h in allow_headers})
        self._allow_credentials = allow_credentials
        self._max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "").startswith(self._exempt_prefix):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")
        if origin is None:
            await self.app(scope, receive, send)
            return

        allowed_origins = await self._get_allowed_origins()

        if scope["method"] == "OPTIONS" and "access-control-request-method" in headers:
            response = self._preflight_response(headers, allowed_origins)
            await response(scope, receive, send)
            return

        wrapped_send = functools.partial(
            self._send, send=send, origin=origin, allowed_origins=allowed_origins
        )
        await self.app(scope, receive, wrapped_send)

    def _preflight_response(self, request_headers: Headers, allowed_origins: Iterable[str]) -> Response:
        requested_origin = request_headers["origin"]
        requested_method = request_headers["access-control-request-method"]
        requested_headers = request_headers.get("access-control-request-headers")

        headers: dict[str, str] = {
            "Vary": "Origin",
            "Access-Control-Allow-Methods": ", ".join(self._allow_methods),
            "Access-Control-Max-Age": str(self._max_age),
        }
        failures: list[str] = []

        if requested_origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = requested_origin
        else:
            failures.append("origin")

        if requested_method not in self._allow_methods:
            failures.append("method")

        if requested_headers is not None:
            for header in (h.strip().lower() for h in requested_headers.split(",")):
                if header not in self._allow_headers_lower:
                    failures.append("headers")
                    break
            else:
                headers["Access-Control-Allow-Headers"] = ", ".join(self._allow_headers_display)

        if self._allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        if failures:
            return PlainTextResponse("Disallowed CORS " + ", ".join(failures), status_code=400, headers=headers)
        return PlainTextResponse("OK", status_code=200, headers=headers)

    async def _send(self, message: Message, *, send: Send, origin: str, allowed_origins: Iterable[str]) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)

        if origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers.add_vary_header("Origin")
            if self._allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"

        await send(message)
