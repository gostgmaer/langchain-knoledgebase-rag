"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


async def _create_model_profile(client) -> str:
    response = await client.post(
        "/api/v1/model-profiles",
        json={
            "name": f"api-test-agent-profile-{uuid4()}",
            "provider": "google",
            "model": "gemini-3.1-flash-lite",
            "context_window": 1_000_000,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_then_list_then_get_agent(client):
    model_profile_id = await _create_model_profile(client)

    created = (
        await client.post(
            "/api/v1/agents",
            json={
                "name": f"api-test-agent-{uuid4()}",
                "system_prompt": "You are a helpful assistant.",
                "llm_provider": "google",
                "llm_model": "gemini-3.1-flash-lite",
                "model_profile_id": model_profile_id,
            },
        )
    ).json()["data"]
    assert created["model_profile_id"] == model_profile_id

    listed = (await client.get("/api/v1/agents")).json()["data"]
    assert any(a["id"] == created["id"] for a in listed["agents"])

    fetched = await client.get(f"/api/v1/agents/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_agent_with_nonexistent_model_profile_returns_400(client):
    response = await client.post(
        "/api/v1/agents",
        json={
            "name": f"api-test-agent-{uuid4()}",
            "system_prompt": "You are a helpful assistant.",
            "llm_provider": "google",
            "llm_model": "gemini-3.1-flash-lite",
            "model_profile_id": str(uuid4()),
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_nonexistent_agent_returns_404(client):
    response = await client.get(f"/api/v1/agents/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_agent_rejects_missing_required_field(client):
    response = await client.post(
        "/api/v1/agents",
        json={"name": f"api-test-agent-{uuid4()}"},
    )
    assert response.status_code == 422
