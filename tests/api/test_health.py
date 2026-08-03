import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_health_check_reports_database_and_redis_healthy(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert body["data"]["database"] == "healthy"
    assert body["data"]["redis"] == "healthy"
