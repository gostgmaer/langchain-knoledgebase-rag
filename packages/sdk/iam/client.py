from __future__ import annotations

import httpx

from packages.config.iam import IAMSettings

from .auth import IAMAuthSDK
from .tennets import IAMTenantsSDK
from .user import IAMUsersSDK


class IAMClient:
    """Facade for the IAM SDK."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: IAMSettings,
    ) -> None:
        self.auth = IAMAuthSDK(
            client,
            settings,
        )

        self.users = IAMUsersSDK(
            client,
            settings,
        )

        self.tenants = IAMTenantsSDK(
            client,
            settings,
        )