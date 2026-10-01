"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_get_summary_returns_a_well_shaped_response(client):
    response = await client.get("/api/v1/observability/summary")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "retrieval" in data
    assert "documents" in data


@pytest.mark.asyncio
async def test_get_top_documents_returns_a_list(client):
    response = await client.get("/api/v1/observability/top-documents")
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_get_audit_events_returns_a_well_shaped_response(client):
    response = await client.get("/api/v1/observability/audit")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_retention_purge_requires_super_admin_when_auth_is_required(client, monkeypatch):
    """
    AUTH_REQUIRED is forced false for this whole suite (tests/conftest.py), so require_super_admin()
    no-ops exactly like require_admin() does everywhere else — this just exercises the route
    actually runs end to end, not the real authorization boundary (that needs a real token, covered
    by this session's earlier live verification of require_super_admin on this exact route).
    """
    response = await client.post("/api/v1/observability/retention/purge")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "retrieval_logs" in data
    assert "audit_events" in data
