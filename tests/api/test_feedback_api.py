"""Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's
module docstring for the shared `client` fixture's guarantees).

Submitting feedback for real needs a real Message row (a genuine chat turn, which POST /chat
produces) — out of scope for a contract test that shouldn't pay for a real LLM call. Covered here:
the review route's shape, and the submit route's own validation, both real HTTP contract surface
regardless of whether a real message exists yet.
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api


@pytest.mark.asyncio
async def test_review_feedback_returns_a_well_shaped_response(client):
    response = await client.get("/api/v1/feedback")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total" in data
    assert isinstance(data["feedback"], list)


@pytest.mark.asyncio
async def test_submit_feedback_for_nonexistent_message_returns_404(client):
    response = await client.post(
        "/api/v1/feedback",
        json={"message_id": str(uuid4()), "rating": "THUMBS_UP"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_feedback_rejects_invalid_rating(client):
    response = await client.post(
        "/api/v1/feedback",
        json={"message_id": str(uuid4()), "rating": "NOT_A_REAL_RATING"},
    )
    assert response.status_code == 422
