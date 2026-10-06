"""
Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's module
docstring for the shared `client` fixture's guarantees). Covers packages/api/routers/
platform_settings.py (docs/BUGS.md item 38) — the list/effective-value shape, overriding and
reverting a setting, and validation. tests/api/test_dynamic_cors.py covers the one setting
(cors_origins) that also needs to be observably *live* through a second system (the CORS
middleware), not just round-trip through this router.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_list_returns_every_known_setting_with_its_env_default(client):
    response = await client.get("/api/v1/platform-settings")
    assert response.status_code == 200
    settings = {s["key"]: s for s in response.json()["data"]["settings"]}

    assert "rate_limit_requests_per_minute" in settings
    assert "cors_origins" in settings
    row = settings["rate_limit_requests_per_minute"]
    assert row["is_overridden"] is False
    assert row["value"] == row["env_default"]
    assert row["kind"] == "int"

    origins = settings["cors_origins"]
    assert origins["kind"] == "string_list"
    assert isinstance(origins["value"], list)


@pytest.mark.asyncio
async def test_patch_overrides_a_setting_and_marks_it_overridden(client):
    response = await client.patch(
        "/api/v1/platform-settings", json={"values": {"rate_limit_requests_per_minute": 42}}
    )
    assert response.status_code == 200
    row = next(s for s in response.json()["data"]["settings"] if s["key"] == "rate_limit_requests_per_minute")
    assert row["value"] == 42
    assert row["is_overridden"] is True

    # Reflected on a fresh GET, not just the PATCH response.
    again = await client.get("/api/v1/platform-settings")
    row_again = next(s for s in again.json()["data"]["settings"] if s["key"] == "rate_limit_requests_per_minute")
    assert row_again["value"] == 42


@pytest.mark.asyncio
async def test_patch_null_reverts_to_the_env_default(client):
    await client.patch("/api/v1/platform-settings", json={"values": {"session_expiry_days": 99}})
    reverted = await client.patch("/api/v1/platform-settings", json={"values": {"session_expiry_days": None}})
    assert reverted.status_code == 200
    row = next(s for s in reverted.json()["data"]["settings"] if s["key"] == "session_expiry_days")
    assert row["is_overridden"] is False
    assert row["value"] == row["env_default"]


@pytest.mark.asyncio
async def test_patch_rejects_an_unknown_key(client):
    response = await client.patch("/api/v1/platform-settings", json={"values": {"not_a_real_setting": 1}})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_an_out_of_range_value(client):
    response = await client.patch(
        "/api/v1/platform-settings", json={"values": {"connector_sync_concurrency": 999}}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_the_wrong_type_for_a_setting(client):
    response = await client.patch(
        "/api/v1/platform-settings", json={"values": {"rate_limit_requests_per_minute": "fast"}}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_a_malformed_string_list_entry(client):
    response = await client.patch("/api/v1/platform-settings", json={"values": {"cors_origins": [""]}})
    assert response.status_code == 422
