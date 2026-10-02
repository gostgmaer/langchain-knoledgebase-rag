"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_get_analytics_summary_returns_a_well_shaped_response(client):
    response = await client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "queries_per_day" in data
    assert "feedback_trends" in data
    assert "top_failing_queries" in data


@pytest.mark.asyncio
async def test_get_analytics_summary_rejects_out_of_range_days(client):
    response = await client.get("/api/v1/analytics/summary", params={"days": 0})
    assert response.status_code == 422
