"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_list_retrievals_returns_a_well_shaped_response(client):
    response = await client.get("/api/v1/retrieval-logs")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total" in data
    assert isinstance(data["retrievals"], list)


@pytest.mark.asyncio
async def test_list_retrievals_respects_pagination_params(client):
    response = await client.get("/api/v1/retrieval-logs", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    assert response.json()["data"]["limit"] == 5


@pytest.mark.asyncio
async def test_get_nonexistent_retrieval_returns_404(client):
    response = await client.get(f"/api/v1/retrieval-logs/{uuid4()}")
    assert response.status_code == 404
