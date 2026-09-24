# Middleware authentication
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from packages.auth.service import AuthService
from packages.config.loader import settings
from packages.infrastructure.container import ApplicationContainer


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Resolves the current user from an `Authorization: Bearer <token>`
    header via the IAM service.

    Fails open: if the header is absent, or IAM rejects the token or
    is unreachable, `request.state.current_user` stays None and
    TenantMiddleware's existing header-or-default fallback (which runs
    before this, see packages/api/middleware/__init__.py's registration
    order) is left untouched. Only a genuinely verified user overrides
    the tenant/user IDs already on request.state — real permission
    enforcement (packages/api/dependencies.py's require_permission)
    only activates once that happens.
    """

    AUTH_HEADER = "Authorization"
    AUTH_SCHEME = "Bearer "

    # Reachable without a token even when AUTH_REQUIRED is on.
    PUBLIC_PREFIXES = ("/api/v1/health", "/api/v1/auth/refresh")
    PUBLIC_PATHS = ("/docs", "/redoc", "/openapi.json")

    @classmethod
    def _is_public(cls, request: Request) -> bool:
        path = request.url.path
        return (
            request.method == "OPTIONS"
            or path in cls.PUBLIC_PATHS
            or path.startswith(cls.PUBLIC_PREFIXES)
        )

    @staticmethod
    def _deny(status_code: int, detail: str) -> Response:
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        return JSONResponse({"detail": detail}, status_code=status_code, headers=headers)

    @inject
    async def dispatch(
        self,
        request: Request,
        call_next,
        auth_service: AuthService = Provide[ApplicationContainer.iam.auth_service],
    ) -> Response:

        request.state.current_user = None

        header = request.headers.get(self.AUTH_HEADER)

        access_token = None
        if header and header.startswith(self.AUTH_SCHEME):
            access_token = header[len(self.AUTH_SCHEME):]

        required = settings.api.auth_required

        if required and not access_token and not self._is_public(request):
            return self._deny(401, "Authentication required.")

        try:
            current_user = await auth_service.resolve(access_token, fail_open=not required)
        except httpx.HTTPError:
            return self._deny(503, "Could not reach the IAM service.")

        if required and access_token and current_user is None and not self._is_public(request):
            return self._deny(401, "Invalid or expired access token.")

        if current_user is not None:
            request.state.current_user = current_user
            request.state.tenant_id = str(current_user.tenant_id)
            request.state.user_id = str(current_user.id)

        return await call_next(request)
