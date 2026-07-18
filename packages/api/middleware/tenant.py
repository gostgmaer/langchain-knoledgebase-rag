# Middleware tenant
from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Resolves the current tenant from the request.

    Expected headers:

        X-Tenant-ID
        X-Organization-ID (optional)

    The middleware stores the resolved values in:

        request.state.tenant_id
        request.state.organization_id
    """

    TENANT_HEADER = "X-Tenant-ID"
    ORGANIZATION_HEADER = "X-Organization-ID"

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        tenant_id = request.headers.get(self.TENANT_HEADER)
        organization_id = request.headers.get(self.ORGANIZATION_HEADER)

        #
        # Skip tenant validation for public endpoints
        #
        if request.url.path.startswith("/health"):
            return await call_next(request)

        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "MissingTenant",
                    "message": "X-Tenant-ID header is required.",
                },
            )

        request.state.tenant_id = tenant_id
        request.state.organization_id = organization_id

        return await call_next(request)