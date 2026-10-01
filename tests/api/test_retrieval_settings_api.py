"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_get_defaults_has_no_overrides(client):
    response = await client.get("/api/v1/retrieval-settings")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["overrides"]["max_results"] is None
    assert data["effective"] == data["defaults"]


@pytest.mark.asyncio
async def test_put_then_get_reflects_the_override(client):
    put_response = await client.put(
        "/api/v1/retrieval-settings",
        json={"max_results": 3, "reranking_enabled": False},
    )
    assert put_response.status_code == 200
    put_data = put_response.json()["data"]
    assert put_data["overrides"]["max_results"] == 3
    assert put_data["effective"]["max_results"] == 3
    assert put_data["effective"]["reranking_enabled"] is False

    get_response = await client.get("/api/v1/retrieval-settings")
    assert get_response.json()["data"]["overrides"]["max_results"] == 3


@pytest.mark.asyncio
async def test_put_rejects_out_of_range_value(client):
    response = await client.put("/api/v1/retrieval-settings", json={"max_results": 0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_null_clears_an_override_back_to_default(client):
    first = await client.put("/api/v1/retrieval-settings", json={"max_results": 3})
    assert first.json()["data"]["overrides"]["max_results"] == 3

    cleared = await client.put("/api/v1/retrieval-settings", json={"max_results": None})
    assert cleared.json()["data"]["overrides"]["max_results"] is None
