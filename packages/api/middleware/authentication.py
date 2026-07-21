# Middleware authentication
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from packages.auth.service import AuthService
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

        current_user = await auth_service.resolve(access_token)

        if current_user is not None:
            request.state.current_user = current_user
            request.state.tenant_id = str(current_user.tenant_id)
            request.state.user_id = str(current_user.id)

        return await call_next(request)
