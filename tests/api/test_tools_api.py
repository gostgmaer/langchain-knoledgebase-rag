"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


def _payload(**overrides):
    body = {
        "name": f"api-test-tool-{uuid4()}",
        "category": "UTILITY",
        "provider": "internal",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_create_then_list_then_get_tool(client):
    created = (await client.post("/api/v1/tool-definitions", json=_payload())).json()["data"]

    listed = (await client.get("/api/v1/tool-definitions")).json()["data"]
    assert any(t["id"] == created["id"] for t in listed["tools"])

    fetched = await client.get(f"/api/v1/tool-definitions/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(client):
    payload = _payload()
    first = await client.post("/api/v1/tool-definitions", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/tool-definitions", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_rejects_invalid_category(client):
    response = await client.post("/api/v1/tool-definitions", json=_payload(category="NOT_REAL"))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_tool_returns_404(client):
    response = await client.get(f"/api/v1/tool-definitions/{uuid4()}")
    assert response.status_code == 404
