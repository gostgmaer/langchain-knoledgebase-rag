from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from packages.api import dependencies as deps
from packages.api.exception_handlers import _is_provider_outage
from packages.api.middleware.authentication import AuthenticationMiddleware
from packages.api.routers.feature_flags import _forbid_unless_may_manage, _may_manage
from packages.auth.service import NoTenantError
from packages.config.loader import settings


def _user(roles, tenant=None, verified=True):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant or uuid4(),
        roles=roles,
        permissions=[],
        is_email_verified=verified,
    )


def _req(user=None, headers=None):
    return SimpleNamespace(state=SimpleNamespace(current_user=user), headers=headers or {})


# ---- tenant override (B4) -------------------------------------------------------
def test_super_admin_may_act_for_another_tenant():
    admin = _user(["super_admin"])
    other = uuid4()

    got = deps.require_uuid_header(_req(admin, {"X-Tenant-ID": str(other)}), "X-Tenant-ID")

    assert got == other


def test_super_admin_without_header_uses_own_tenant():
    admin = _user(["super_admin"])

    assert deps.require_uuid_header(_req(admin), "X-Tenant-ID") == admin.tenant_id


@pytest.mark.parametrize("roles", [["member"], ["tenant_admin"], ["admin"]])
def test_everyone_else_cannot_override_the_tenant(roles):
    user = _user(roles)

    got = deps.require_uuid_header(_req(user, {"X-Tenant-ID": str(uuid4())}), "X-Tenant-ID")

    assert got == user.tenant_id


def test_super_admin_invalid_override_is_a_400():
    with pytest.raises(HTTPException) as err:
        deps.require_uuid_header(_req(_user(["super_admin"]), {"X-Tenant-ID": "nope"}), "X-Tenant-ID")

    assert err.value.status_code == 400


# ---- feature flags (B1) -----------------------------------------------------------
def test_tenant_admin_manages_only_own_tenant_flags():
    admin = _user(["tenant_admin"])

    assert _may_manage(admin.tenant_id, admin) is True
    assert _may_manage(uuid4(), admin) is False
    assert _may_manage(None, admin) is False  # global flag


def test_super_admin_manages_global_and_any_tenant_flags():
    root = _user(["super_admin"])

    assert _may_manage(None, root) is True
    assert _may_manage(uuid4(), root) is True


def test_forbid_raises_403_for_a_global_flag():
    with pytest.raises(HTTPException) as err:
        _forbid_unless_may_manage(None, _user(["tenant_admin"]))

    assert err.value.status_code == 403


def test_legacy_open_mode_without_a_user_allows_everything():
    assert _may_manage(None, None) is True


@pytest.mark.asyncio
async def test_require_admin_rejects_a_member(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)

    with pytest.raises(HTTPException) as err:
        await deps.require_admin()(_user(["member"]))

    assert err.value.status_code == 403


@pytest.mark.asyncio
async def test_require_super_admin(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)
    check = deps.require_super_admin()

    await check(_user(["super_admin"]))
    with pytest.raises(HTTPException) as err:
        await check(_user(["tenant_admin"]))

    assert err.value.status_code == 403


# ---- provider outage (B7) -----------------------------------------------------------
def _exc(module, name, **attrs):
    cls = type(name, (Exception,), {"__module__": module})
    err = cls("boom")
    for key, value in attrs.items():
        setattr(err, key, value)
    return err


def test_gemini_overload_is_a_provider_outage():
    assert _is_provider_outage(_exc("google.genai.errors", "ServerError", code=503)) is True


def test_outage_is_found_inside_an_exception_group():
    inner = _exc("google.genai.errors", "ServerError", code=503)
    group = SimpleNamespace(exceptions=[inner])
    wrapper = Exception("wrapped")
    wrapper.__cause__ = None
    wrapper.exceptions = group.exceptions

    assert _is_provider_outage(wrapper) is True


def test_ordinary_bugs_are_not_reported_as_provider_outages():
    assert _is_provider_outage(ValueError("bad input")) is False
    assert _is_provider_outage(_exc("google.genai.errors", "ClientError", code=400)) is False


# ---- middleware (B10 + no-workspace) ------------------------------------------------
def _http_request(path="/api/v1/knowledge-bases", token="tok"):
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [(b"authorization", f"Bearer {token}".encode())] if token else [],
        "query_string": b"",
    }
    return Request(scope)


class _FakeAuth:
    def __init__(self, result=None, raises=None):
        self._result, self._raises = result, raises

    async def resolve(self, _token, *, fail_open=True):
        if self._raises:
            raise self._raises
        return self._result


async def _next(_request):
    return SimpleNamespace(status_code=200)


@pytest.mark.asyncio
async def test_unverified_email_is_refused_when_required(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)
    monkeypatch.setattr(settings.api, "require_verified_email", True)
    mw = AuthenticationMiddleware(app=None)

    resp = await mw.dispatch(_http_request(), _next, auth_service=_FakeAuth(_user(["member"], verified=False)))

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verified_email_passes(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)
    monkeypatch.setattr(settings.api, "require_verified_email", True)
    mw = AuthenticationMiddleware(app=None)

    resp = await mw.dispatch(_http_request(), _next, auth_service=_FakeAuth(_user(["member"], verified=True)))

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unverified_email_is_fine_when_not_required(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)
    monkeypatch.setattr(settings.api, "require_verified_email", False)
    mw = AuthenticationMiddleware(app=None)

    resp = await mw.dispatch(_http_request(), _next, auth_service=_FakeAuth(_user(["member"], verified=False)))

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_no_workspace_is_403_but_health_stays_public(monkeypatch):
    monkeypatch.setattr(settings.api, "auth_required", True)
    mw = AuthenticationMiddleware(app=None)
    fake = _FakeAuth(raises=NoTenantError())

    blocked = await mw.dispatch(_http_request("/api/v1/knowledge-bases"), _next, auth_service=fake)
    health = await mw.dispatch(_http_request("/api/v1/health"), _next, auth_service=fake)

    assert blocked.status_code == 403
    assert health.status_code == 200
