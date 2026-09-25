# Auth service
from __future__ import annotations

import httpx
from pydantic import ValidationError

from packages.sdk.common.exceptions import SDKException
from packages.sdk.iam.client import IAMClient
from packages.sdk.iam.models import CurrentUser
from packages.shared.logging import get_logger

logger = get_logger(__name__)


class NoTenantError(Exception):
    """
    IAM verified the token, but the account is not a member of any tenant
    (its /auth/me profile has no `tenantId` - e.g. self-registered and never
    invited to a workspace). Distinct from "invalid token" so callers can answer
    403 with an actionable message instead of crashing with a 500.
    """


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
        *,
        fail_open: bool = True,
    ) -> CurrentUser | None:
        """With fail_open=False an unreachable IAM raises httpx.HTTPError
        (so the caller can answer 503) instead of being treated as "no user"."""

        if not access_token:
            return None

        try:
            return await self._client.auth.get_current_user(access_token)
        except ValidationError as exc:
            # The profile came back without a required field. The only one that
            # legitimately goes missing is tenantId (an account with no workspace).
            missing_tenant = any(
                err.get("type") == "missing" and "tenantId" in err.get("loc", ())
                for err in exc.errors()
            )
            if missing_tenant:
                if not fail_open:
                    raise NoTenantError from exc
                logger.warning("IAM user has no tenant, falling back to default identity")
                return None
            raise
        except httpx.HTTPError as exc:
            if not fail_open:
                raise
            logger.warning(
                "IAM auth failed, falling back to default identity",
                error=str(exc),
            )
            return None
        except SDKException as exc:
            logger.warning(
                "IAM auth failed, falling back to default identity",
                error=str(exc),
            )
            return None
