from __future__ import annotations

import httpx

from packages.config.iam import IAMSettings
from packages.sdk.common.base_client import BaseClient

from .endpoints import IAMEndpoints
from .models import User


class IAMUsersSDK(BaseClient):
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: IAMSettings,
    ) -> None:
        super().__init__(
            client=client,
            base_url=settings.base_url,
        )

    async def get_user(
        self,
        user_id: str,
        access_token: str | None = None,
    ) -> User:
        """
        `access_token`: the caller's own bearer token, forwarded as-is — same idiom as
        `IAMTenantsSDK.get_tenant()`. Found live (not just by inspection): the original version
        of this method sent no Authorization header at all and IAM correctly rejected every call
        with 401 "Access denied. No token provided" — this had never actually been exercised
        before (see User's own docstring in models.py for the matching field-name bug found at
        the same time).
        """

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None

        response = await self._get(
            IAMEndpoints.USER.format(
                user_id=user_id,
            ),
            headers=headers,
        )

        return User.model_validate(
            self._unwrap(response),
        )

    async def list_users(
        self,
        tenant_id: str,
        access_token: str | None = None,
        *,
        limit: int = 100,
    ) -> list[User]:
        """
        `GET /users?tenantId=...` — real members of a tenant (docs/BUGS.md item 32), not just
        pending invitations. `tenantId` is accepted from any caller but only actually honored for
        a super_admin token; IAM silently scopes every other caller to their own tenant regardless
        of what's passed here (confirmed live) — correct either way for this app's own callers,
        who are always either super_admin (legitimately browsing another tenant) or already
        looking at their own.
        """

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None

        response = await self._get(
            IAMEndpoints.USERS,
            headers=headers,
            params={"tenantId": tenant_id, "limit": limit},
        )

        return [User.model_validate(row) for row in self._unwrap(response)]