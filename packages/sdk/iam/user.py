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
    ) -> User:

        response = await self._get(
            IAMEndpoints.USER.format(
                user_id=user_id,
            )
        )

        return User.model_validate(
            response.json(),
        )