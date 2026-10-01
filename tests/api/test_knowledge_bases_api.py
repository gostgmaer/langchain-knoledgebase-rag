"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_create_then_list_then_get_knowledge_base(client):
    name = f"api-test-kb-{uuid4()}"
    created = (await client.post("/api/v1/knowledge-bases", json={"name": name})).json()["data"]
    assert created["name"] == name
    assert created["document_count"] == 0

    listed = (await client.get("/api/v1/knowledge-bases")).json()["data"]
    assert any(kb["id"] == created["id"] for kb in listed["knowledge_bases"])

    fetched = await client.get(f"/api/v1/knowledge-bases/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(client):
    name = f"api-test-kb-{uuid4()}"
    first = await client.post("/api/v1/knowledge-bases", json={"name": name})
    assert first.status_code == 201

    second = await client.post("/api/v1/knowledge-bases", json={"name": name})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_delete_empty_knowledge_base_succeeds(client):
    created = (
        await client.post("/api/v1/knowledge-bases", json={"name": f"api-test-kb-{uuid4()}"})
    ).json()["data"]

    response = await client.delete(f"/api/v1/knowledge-bases/{created['id']}")
    assert response.status_code == 200

    fetched = await client.get(f"/api/v1/knowledge-bases/{created['id']}")
    assert fetched.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_knowledge_base_returns_404(client):
    response = await client.get(f"/api/v1/knowledge-bases/{uuid4()}")
    assert response.status_code == 404
