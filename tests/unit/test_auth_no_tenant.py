from __future__ import annotations

from uuid import uuid4

import pytest

from packages.auth.service import AuthService, NoTenantError
from packages.sdk.iam.models import CurrentUser


class _Auth:
    def __init__(self, payload):
        self._payload = payload

    async def get_current_user(self, _token):
        return CurrentUser.model_validate(self._payload)


class _Client:
    def __init__(self, payload):
        self.auth = _Auth(payload)


def _profile(**over):
    base = {"id": str(uuid4()), "email": "a@example.com", "roles": ["member"], "permissions": []}
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_account_without_tenant_raises_no_tenant_when_enforced():
    service = AuthService(_Client(_profile()))  # no tenantId

    with pytest.raises(NoTenantError):
        await service.resolve("token", fail_open=False)


@pytest.mark.asyncio
async def test_account_without_tenant_falls_back_when_not_enforced():
    service = AuthService(_Client(_profile()))

    assert await service.resolve("token", fail_open=True) is None


@pytest.mark.asyncio
async def test_account_with_tenant_resolves():
    tenant = str(uuid4())
    service = AuthService(_Client(_profile(tenantId=tenant)))

    user = await service.resolve("token", fail_open=False)

    assert str(user.tenant_id) == tenant


@pytest.mark.asyncio
async def test_other_validation_errors_are_not_swallowed():
    service = AuthService(_Client({"tenantId": str(uuid4())}))  # missing id

    with pytest.raises(Exception):
        await service.resolve("token", fail_open=False)
