from __future__ import annotations


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

    return headers
