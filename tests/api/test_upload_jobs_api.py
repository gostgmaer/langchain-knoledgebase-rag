"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees)."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_get_nonexistent_upload_job_returns_404(client):
    response = await client.get(f"/api/v1/upload-jobs/{uuid4()}")
    assert response.status_code == 404
