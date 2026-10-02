"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_create_then_list_then_get_prompt(client):
    name = f"api-test-prompt-{uuid4()}"
    created = (
        await client.post("/api/v1/prompts", json={"name": name, "category": "RAG"})
    ).json()["data"]
    assert created["name"] == name

    listed = (await client.get("/api/v1/prompts")).json()["data"]
    assert any(p["id"] == created["id"] for p in listed["prompts"])

    fetched = await client.get(f"/api/v1/prompts/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(client):
    name = f"api-test-prompt-{uuid4()}"
    first = await client.post("/api/v1/prompts", json={"name": name, "category": "SYSTEM"})
    assert first.status_code == 201

    second = await client.post("/api/v1/prompts", json={"name": name, "category": "SYSTEM"})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_rejects_invalid_category(client):
    response = await client.post(
        "/api/v1/prompts",
        json={"name": f"api-test-prompt-{uuid4()}", "category": "NOT_A_REAL_CATEGORY"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_prompt_returns_404(client):
    response = await client.get(f"/api/v1/prompts/{uuid4()}")
    assert response.status_code == 404
