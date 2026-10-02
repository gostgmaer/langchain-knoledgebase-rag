from __future__ import annotations

import httpx

from packages.config.iam import IAMSettings
from packages.sdk.common.base_client import BaseClient

from .endpoints import IAMEndpoints
from .models import Tenant


class IAMTenantsSDK(BaseClient):
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: IAMSettings,
    ) -> None:
        super().__init__(
            client=client,
            base_url=settings.base_url,
        )

    async def get_tenant(
        self,
        tenant_id: str,
        access_token: str | None = None,
    ) -> Tenant:
        """
        `access_token`: the caller's own bearer token, forwarded as-is — IAM's
        `/tenants/:id` is a user-context endpoint (same idiom as `auth.refresh_token()`
        taking the caller's own refresh token), not one this SDK has a separate
        service credential for.
        """

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None

        response = await self._get(
            IAMEndpoints.TENANT.format(
                tenant_id=tenant_id,
            ),
            headers=headers,
        )

        return Tenant.model_validate(
            self._unwrap(response),
        )