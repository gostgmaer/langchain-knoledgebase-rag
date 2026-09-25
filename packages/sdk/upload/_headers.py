from __future__ import annotations

import hashlib
import hmac

# Stable id used to sign requests that have no end user.
SERVICE_USER_ID = "00000000-0000-0000-0000-000000000002"


def identity_headers(tenant_id: str, user_id: str | None = None) -> dict[str, str]:
    """
    The identity headers the real Upload Service reads as trusted
    facts (INTEGRATION_GUIDE.md §4) — it does no authentication of its
    own, so whatever's sent here becomes `tenantId`/`uploader` on the
    stored file. Omitting `X-Tenant-Id` doesn't error; it silently
    falls back to the service's own `DEFAULT_TENANT_ID`, which is
    exactly the bug this helper exists to prevent — every caller's
    file landing under the same default tenant regardless of which of
    our own tenants actually uploaded it.
    """

    headers = {"X-Tenant-Id": tenant_id}

    if user_id:
        headers["X-User-Id"] = user_id

    _sign(headers, user_id)

    return headers


def _sign(headers: dict[str, str], user_id: str | None) -> None:
    """
    Adds the gateway-style signed identity when a shared secret is
    configured. The Upload Service recomputes
    HMAC-SHA256(secret, "<userId>:<userEmail>:<userRole>") and compares it to
    X-Gateway-Hmac; without a valid one it answers 401 "Missing gateway
    signature" (its GATEWAY_AUTH_REQUIRED default). Email is sent empty - the
    service only uses it as part of the signed string.
    """

    from packages.config.loader import settings

    upload = settings.upload_service
    if not upload.hmac_secret:
        return

    # The service rejects a signed request that has no user id; uploads made
    # without one (e.g. background jobs) use the tenant-agnostic service id.
    identity = user_id or SERVICE_USER_ID
    role = upload.service_role

    # "<userId>:<userEmail>:<userRole>" with an empty email.
    payload = f"{identity}::{role}"
    signature = hmac.new(
        upload.hmac_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    headers["X-User-Id"] = identity
    headers["X-User-Email"] = ""
    headers["X-User-Role"] = role
    headers["X-Gateway-Hmac"] = signature
