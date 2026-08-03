"""
Real HTTP requests against the real FastAPI app (via the `client`
fixture — ASGITransport, no mocking of routing/serialization/DI), real
Postgres underneath (rolled back after the test). RBAC is deterministically
disabled for the duration of these tests (see conftest.py's
_RBACDisabledFeatureFlagService) so they don't depend on whatever the
real `enable_rbac` flag's live value happens to be.

Every flag key is uuid4()-suffixed for the same reason
tests/integration/test_feature_flag_repository.py's are: this dev
database already has real, committed feature-flag rows from this
session's own earlier manual verification work.
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


def _unique_key() -> str:
    return f"api_test_flag_{uuid4()}"


@pytest.mark.asyncio
async def test_create_then_get_feature_flag(client):
    key = _unique_key()

    create_response = await client.post(
        "/api/v1/feature-flags",
        json={"key": key, "enabled": True, "description": "created by a test"},
    )
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["key"] == key
    assert created["enabled"] is True

    get_response = await client.get(f"/api/v1/feature-flags/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_duplicate_key_and_scope_returns_409(client):
    key = _unique_key()

    first = await client.post("/api/v1/feature-flags", json={"key": key, "enabled": False})
    assert first.status_code == 201

    second = await client.post("/api/v1/feature-flags", json={"key": key, "enabled": True})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_nonexistent_flag_returns_404(client):
    response = await client.get(f"/api/v1/feature-flags/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_flag_flips_enabled_and_persists(client):
    key = _unique_key()
    created = (
        await client.post("/api/v1/feature-flags", json={"key": key, "enabled": False})
    ).json()["data"]
    assert created["enabled"] is False

    toggle_response = await client.patch(
        f"/api/v1/feature-flags/{created['id']}/toggle",
        json={"enabled": True},
    )
    assert toggle_response.status_code == 200
    assert toggle_response.json()["data"]["enabled"] is True

    refetched = await client.get(f"/api/v1/feature-flags/{created['id']}")
    assert refetched.json()["data"]["enabled"] is True


@pytest.mark.asyncio
async def test_toggle_nonexistent_flag_returns_404(client):
    response = await client.patch(
        f"/api/v1/feature-flags/{uuid4()}/toggle",
        json={"enabled": True},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_flag_rejects_unknown_fields(client):
    response = await client.post(
        "/api/v1/feature-flags",
        json={"key": _unique_key(), "enabled": True, "not_a_real_field": 123},
    )

    assert response.status_code == 422
