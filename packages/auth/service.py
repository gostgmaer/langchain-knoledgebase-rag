# Auth service
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from packages.api.permissions import Permission
from packages.auth.api_keys import hash_api_key, looks_like_api_key
from packages.infrastructure.repositories.api_key import ApiKeyRepository
from packages.sdk.common.exceptions import SDKException
from packages.sdk.iam.client import IAMClient
from packages.sdk.iam.models import CurrentUser
from packages.shared.logging import get_logger

if TYPE_CHECKING:
    from packages.domain.models.api_key import ApiKey

logger = get_logger(__name__)

# Every code this app defines, granted in full to an API key's synthetic identity (see
# _resolve_api_key below) — matches exactly what the real "admin" role already has via IAM's own
# role_permissions mapping (scripts/iam_rbac_seed.sql), not a privilege escalation.
_ALL_PERMISSION_CODES = [
    value for key, value in vars(Permission).items() if not key.startswith("_") and isinstance(value, str)
]


class NoTenantError(Exception):
    """
    IAM verified the token, but the account is not a member of any tenant
    (its /auth/me profile has no `tenantId` - e.g. self-registered and never
    invited to a workspace). Distinct from "invalid token" so callers can answer
    403 with an actionable message instead of crashing with a 500.
    """


class AuthService:
    """
    Resolves the current user from a bearer token — either a real IAM-issued one (verified
    against IAM) or one of this app's own API keys (docs/BUGS.md item 33, verified against this
    app's own `api_keys` table instead).

    Fails open: if the token is missing, or the IAM service is
    unreachable or rejects the token, this returns None rather than
    raising. Callers fall back to the existing default-tenant/default-
    user behavior — real permission enforcement only activates once a
    token is actually verified.
    """

    def __init__(
        self,
        client: IAMClient,
        api_key_session_factory: async_sessionmaker | None = None,
    ) -> None:
        self._client = client
        # Optional (not every AuthService construction has a DB available, e.g. a bare script) —
        # an API-key-shaped token with no session factory wired in just fails closed below,
        # same as a real token IAM can't verify.
        self._api_key_session_factory = api_key_session_factory

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

        if looks_like_api_key(access_token):
            return await self._resolve_api_key(access_token)

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

    async def _resolve_api_key(self, raw_key: str) -> CurrentUser | None:
        """
        No IAM round-trip at all — this app's own `api_keys` table is the system of record for
        these. Returns None (never raises) for anything wrong with the key: missing, revoked,
        expired, or no DB available to check against — the caller treats that identically to an
        invalid IAM token (401 if auth is required, same as the existing path above).
        """
        if self._api_key_session_factory is None:
            logger.warning("API key presented but no DB session factory is configured")
            return None

        key_hash = hash_api_key(raw_key)

        async with self._api_key_session_factory() as session:
            repo = ApiKeyRepository(session)
            key: ApiKey | None = await repo.get_by_hash(key_hash)

            if key is None or not key.is_active:
                return None
            if key.expires_at is not None and key.expires_at < datetime.now(UTC):
                return None

            await repo.touch_last_used(key)
            await session.commit()

            return CurrentUser(
                id=key.created_by_user_id,
                tenant_id=key.tenant_id,
                email=key.created_by_email,
                roles=["admin"],
                permissions=_ALL_PERMISSION_CODES,
                is_active=True,
                is_email_verified=True,
                is_super_admin=False,
            )
