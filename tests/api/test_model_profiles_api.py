"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


def _payload(**overrides):
    body = {
        "name": f"api-test-profile-{uuid4()}",
        "provider": "google",
        "model": "gemini-3.1-flash-lite",
        "context_window": 1_000_000,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_create_then_list_then_get_model_profile(client):
    created = (await client.post("/api/v1/model-profiles", json=_payload())).json()["data"]
    assert created["provider"] == "google"

    listed = (await client.get("/api/v1/model-profiles")).json()["data"]
    assert any(p["id"] == created["id"] for p in listed["model_profiles"])

    fetched = await client.get(f"/api/v1/model-profiles/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(client):
    payload = _payload()
    first = await client.post("/api/v1/model-profiles", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/model-profiles", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_nonexistent_model_profile_returns_404(client):
    response = await client.get(f"/api/v1/model-profiles/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_rejects_unknown_fields(client):
    response = await client.post("/api/v1/model-profiles", json=_payload(not_a_real_field=1))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_missing_required_field(client):
    body = _payload()
    del body["context_window"]
    response = await client.post("/api/v1/model-profiles", json=body)
    assert response.status_code == 422
