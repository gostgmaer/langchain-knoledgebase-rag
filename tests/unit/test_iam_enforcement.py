from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from packages.api import dependencies as deps
from packages.config.loader import settings


def _request(user=None, headers=None):
    return SimpleNamespace(
        state=SimpleNamespace(current_user=user),
        headers=headers or {},
    )


def _user(roles):
    return SimpleNamespace(id=uuid4(), tenant_id=uuid4(), roles=roles, permissions=[])


def test_verified_identity_beats_spoofed_headers():
    user = _user(["member"])
    request = _request(user, {"X-Tenant-ID": str(uuid4()), "X-User-ID": str(uuid4())})

    assert deps.require_uuid_header(request, "X-Tenant-ID") == user.tenant_id
    assert deps.require_uuid_header(request, "X-User-ID") == user.id


def test_headers_still_used_without_verified_user():
    tenant = uuid4()
    request = _request(None, {"X-Tenant-ID": str(tenant)})

    assert deps.require_uuid_header(request, "X-Tenant-ID") == tenant


@pytest.mark.asyncio
async def test_require_admin_noop_when_auth_not_required(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", False)
    await deps.require_admin()(None)


@pytest.mark.asyncio
async def test_require_admin_enforces_roles(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)
    check = deps.require_admin()

    with pytest.raises(HTTPException) as anon:
        await check(None)
    assert anon.value.status_code == 401

    with pytest.raises(HTTPException) as member:
        await check(_user(["member"]))
    assert member.value.status_code == 403

    await check(_user(["tenant_admin"]))
