# Auth service
from __future__ import annotations

import httpx

from packages.sdk.common.exceptions import SDKException
from packages.sdk.iam.client import IAMClient
from packages.sdk.iam.models import CurrentUser
from packages.shared.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    """
    Resolves the current user from a bearer token via the IAM service.

    Fails open: if the token is missing, or the IAM service is
    unreachable or rejects the token, this returns None rather than
    raising. Callers fall back to the existing default-tenant/default-
    user behavior — real permission enforcement only activates once a
    token is actually verified.
    """

    def __init__(
        self,
        client: IAMClient,
    ) -> None:
        self._client = client

    async def resolve(
        self,
        access_token: str | None,
    ) -> CurrentUser | None:

        if not access_token:
            return None

        try:
            return await self._client.auth.get_current_user(access_token)
        except (SDKException, httpx.HTTPError) as exc:
            logger.warning(
                "IAM auth failed, falling back to default identity",
                error=str(exc),
            )
            return None
