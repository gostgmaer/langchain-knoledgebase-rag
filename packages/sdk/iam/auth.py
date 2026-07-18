from __future__ import annotations

from http import HTTPMethod

import httpx

from packages.config.iam import IAMSettings
from packages.sdk.common.base_client import BaseClient

from .endpoints import IAMEndpoints
from .models import CurrentUser, IntrospectionResponse, ServiceToken


class IAMAuthSDK(BaseClient):
    """IAM authentication SDK."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: IAMSettings,
    ) -> None:
        super().__init__(
            client=client,
            base_url=str(settings.url),
        )

        self._settings = settings

    async def health(self) -> bool:
        """Check IAM health."""

        await self._get(IAMEndpoints.HEALTH)
        return True

    async def get_service_token(self) -> ServiceToken:
        """Request a service-to-service access token."""

        response = await self._post(
            IAMEndpoints.TOKEN,
            json={
                "grant_type": "client_credentials",
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
            },
        )

        return ServiceToken.model_validate(response.json())

    async def introspect(
        self,
        session_id: str,
    ) -> IntrospectionResponse:
        """Validate a session and retrieve fresh permissions."""

        response = await self._post(
            IAMEndpoints.INTROSPECT,
            json={
                "sessionId": session_id,
            },
            headers={
                "x-api-key": self._settings.introspection_api_key,
            },
        )

        return IntrospectionResponse.model_validate(
            response.json(),
        )

    async def get_current_user(
        self,
        access_token: str,
    ) -> CurrentUser:
        """Retrieve the authenticated user's profile."""

        response = await self._get(
            IAMEndpoints.ME,
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        return CurrentUser.model_validate(
            response.json(),
        )