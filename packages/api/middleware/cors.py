# Middleware CORS
from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send


class SelectiveCORSMiddleware(CORSMiddleware):
    """
    Starlette's own `CORSMiddleware`, except it never intercepts paths under `exempt_prefix`.

    `CORSMiddleware` answers *every* OPTIONS preflight in the app itself, before the request ever
    reaches a route — by design, confirmed live: a real browser preflight to a path under
    `exempt_prefix` came back `400` from this middleware's own `allow_origins` check, and the
    route's own `@router.options(...)` handler (packages/api/routers/widget.py) never ran at all.
    That's correct for every *other* route (this app's one static, startup-time allowlist,
    `settings.api.cors_origins`), but the public embeddable widget's allowed origins are
    per-agent, stored in the database, decided by a tenant admin at runtime — nothing a static
    list fixed at process startup can express. Those paths handle their own CORS end to end
    (preflight and the real response's headers) and need this middleware to just get out of the
    way, not merge its own static policy with theirs.
    """

    def __init__(self, app, *, exempt_prefix: str, **kwargs: object) -> None:
        super().__init__(app, **kwargs)
        self._exempt_prefix = exempt_prefix
        self._inner_app = app  # the raw app this middleware wraps — bypasses our own __call__

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith(self._exempt_prefix):
            await self._inner_app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
