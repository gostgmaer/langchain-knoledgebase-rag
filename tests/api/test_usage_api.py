"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_get_usage_returns_a_well_shaped_response_even_with_no_data(client):
    response = await client.get("/api/v1/usage")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "prompt_tokens" in data
    assert "completion_tokens" in data
    assert "total_tokens" in data
    assert isinstance(data["daily"], list)


@pytest.mark.asyncio
async def test_get_usage_respects_days_query_param(client):
    response = await client.get("/api/v1/usage", params={"days": 7})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_usage_rejects_out_of_range_days(client):
    response = await client.get("/api/v1/usage", params={"days": 0})
    assert response.status_code == 422

    response = await client.get("/api/v1/usage", params={"days": 400})
    assert response.status_code == 422
