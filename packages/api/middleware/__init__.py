# Middleware init
from __future__ import annotations

from fastapi import FastAPI

from packages.config.loader import settings

from .authentication import AuthenticationMiddleware
from .cors import DynamicCORSMiddleware
from .logging import LoggingMiddleware
from .metrics import MetricsMiddleware
from .rate_limit import RateLimitMiddleware
from .request_id import RequestIdMiddleware
from .security_headers import SecurityHeadersMiddleware
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
    # Rate limiting (Production hardening's own pending gap — see
    # packages/api/middleware/rate_limit.py). Registered here, just
    # inside Metrics/CORS, so abusive traffic is rejected before it
    # costs a request-id, a log line, tenant resolution, or an IAM
    # round-trip.
    #
    app.add_middleware(
        RateLimitMiddleware,
    )

    #
    # Metrics (Production hardening's own other pending gap — see
    # packages/api/middleware/metrics.py). Registered just inside CORS
    # so it still times/counts requests RateLimitMiddleware rejects
    # (a 429 is a real, countable response), not just ones that reach
    # the route.
    #
    app.add_middleware(
        MetricsMiddleware,
    )

    #
    # Security headers (docs/BUILD_STATUS.md gap #2). Registered just
    # inside CORS so it still stamps headers on responses CORS itself
    # short-circuits (a preflight OPTIONS), and on every real response.
    #
    app.add_middleware(
        SecurityHeadersMiddleware,
    )

    #
    # CORS (outermost — must run first on the way in, to answer
    # preflight OPTIONS requests before TenantMiddleware/auth ever see
    # them). Explicit custom headers listed since browsers block
    # X-Tenant-ID/X-User-ID by default unless a CORS response allows
    # them by name. frontend/ (a separate Next.js origin in dev) is
    # the reason this exists at all — see packages/config/api.py.
    #
    # Exempts /api/v1/widget/ — the embeddable chat widget's allowed
    # origins are per-agent, stored in the database by a tenant admin
    # at runtime, not expressible in this one platform-wide list. That
    # router (packages/api/routers/widget.py) answers its own preflight
    # and sets its own per-request CORS headers; see DynamicCORSMiddleware's
    # own docstring for why this is necessary, not just tidy.
    #
    # Reads the allowed-origins list fresh on every request through
    # PlatformSettingsService (docs/BUGS.md item 38), not a list fixed
    # at process startup — an admin's change on the Platform Settings
    # page takes effect without a restart. `app.state.container` is
    # looked up lazily, inside the closure, since it isn't set yet at
    # this point in startup.
    #
    async def _allowed_origins() -> list[str]:
        container = app.state.container
        return await container.platform_settings.service().get("cors_origins")

    app.add_middleware(
        DynamicCORSMiddleware,
        exempt_prefix=f"{settings.api.api_prefix}/widget/",
        get_allowed_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["X-Tenant-ID", "X-User-ID", "Content-Type", "Authorization"],
    )