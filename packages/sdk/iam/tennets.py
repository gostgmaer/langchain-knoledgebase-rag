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
    ) -> Tenant:

        response = await self._get(
            IAMEndpoints.TENANT.format(
                tenant_id=tenant_id,
            )
        )

        return Tenant.model_validate(
            response.json(),
        )