# Middleware tenant
from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Resolves the current tenant from the request.

    Expected headers:

        X-Tenant-ID
        X-Organization-ID (optional)

    The middleware stores the resolved values in:

        request.state.tenant_id
        request.state.organization_id

    Falls back to a fixed, well-known DEFAULT_TENANT_ID when the header
    is absent — there's no real auth/IAM wired up yet (see docs/BUILD_STATUS.md),
    so this doesn't weaken anything that was actually enforced; it just
    makes the API testable without hand-crafting a tenant header first.
    """

    TENANT_HEADER = "X-Tenant-ID"
    ORGANIZATION_HEADER = "X-Organization-ID"

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        tenant_id = request.headers.get(self.TENANT_HEADER) or DEFAULT_TENANT_ID
        organization_id = request.headers.get(self.ORGANIZATION_HEADER)

        request.state.tenant_id = tenant_id
        request.state.organization_id = organization_id

        return await call_next(request)
