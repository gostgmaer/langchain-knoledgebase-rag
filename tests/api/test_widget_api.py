"""
Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's module
docstring for the shared `client` fixture's guarantees). Covers the agent-side widget management
endpoints and the public /widget/* router's own logic — origin validation, 404s, CORS headers,
preflight — everything reachable without actually invoking chat_service (no established pattern
exists in this test suite for mocking the LLM/graph pipeline at the HTTP level; that's deliberately
out of scope here, same as every other API test touching /chat).
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.api

ALLOWED_ORIGIN = "https://shop.example.com"


async def _create_agent(client) -> dict:
    # `model` is uuid4()-suffixed, not just `name` — model_profiles has a UNIQUE(provider, model)
    # constraint, and this dev database already has a real, committed GOOGLE/gemini-3.1-flash-lite
    # row from this session's own earlier manual verification work (same reasoning as
    # test_feature_flags_api.py's module docstring on uuid4()-suffixing its own flag keys).
    profile = (
        await client.post(
            "/api/v1/model-profiles",
            json={
                "name": f"api-test-widget-profile-{uuid4()}",
                "provider": "GOOGLE",
                "model": f"gemini-3.1-flash-lite-{uuid4()}",
                "context_window": 1_000_000,
            },
        )
    ).json()["data"]

    agent = (
        await client.post(
            "/api/v1/agents",
            json={
                "name": f"api-test-widget-agent-{uuid4()}",
                "description": "Ask me about our products.",
                "system_prompt": "You are a helpful storefront assistant.",
                "llm_provider": "GOOGLE",
                "llm_model": "gemini-3.1-flash-lite",
                "model_profile_id": profile["id"],
            },
        )
    ).json()["data"]
    return agent


async def _enable_widget(client, agent_id: str, origins: list[str] | None = None) -> dict:
    # `origins is None` means "use the default", distinct from an explicitly empty list — `origins
    # or [ALLOWED_ORIGIN]` would be wrong here since `[] or x` evaluates to `x` in Python, silently
    # replacing a deliberately-empty list with the default and defeating the one test that needs it.
    body_origins = [ALLOWED_ORIGIN] if origins is None else origins
    response = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"widget_enabled": True, "widget_allowed_origins": body_origins},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.asyncio
async def test_enabling_the_widget_mints_a_public_id_once(client):
    agent = await _create_agent(client)
    assert agent["widget_enabled"] is False and agent["widget_public_id"] is None

    enabled = await _enable_widget(client, agent["id"])
    assert enabled["widget_enabled"] is True
    assert enabled["widget_public_id"] and enabled["widget_public_id"].startswith("wgt_")

    # Re-saving with widget_enabled still true does not mint a second id.
    again = await _enable_widget(client, agent["id"])
    assert again["widget_public_id"] == enabled["widget_public_id"]


@pytest.mark.asyncio
async def test_disabling_then_reenabling_keeps_the_same_public_id(client):
    agent = await _create_agent(client)
    enabled = await _enable_widget(client, agent["id"])
    public_id = enabled["widget_public_id"]

    disabled = (
        await client.patch(f"/api/v1/agents/{agent['id']}", json={"widget_enabled": False})
    ).json()["data"]
    assert disabled["widget_enabled"] is False
    assert disabled["widget_public_id"] == public_id  # a customer's already-embedded snippet survives

    reenabled = await _enable_widget(client, agent["id"])
    assert reenabled["widget_public_id"] == public_id


@pytest.mark.asyncio
async def test_malformed_origin_is_rejected(client):
    agent = await _create_agent(client)
    response = await client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"widget_enabled": True, "widget_allowed_origins": ["not-a-url"]},
    )
    assert response.status_code == 422

    with_path = await client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"widget_enabled": True, "widget_allowed_origins": ["https://example.com/some/path"]},
    )
    assert with_path.status_code == 422


@pytest.mark.asyncio
async def test_rotate_widget_id_invalidates_the_previous_one(client):
    agent = await _create_agent(client)
    enabled = await _enable_widget(client, agent["id"])
    old_id = enabled["widget_public_id"]

    rotated = (await client.post(f"/api/v1/agents/{agent['id']}/widget/rotate")).json()["data"]
    new_id = rotated["widget_public_id"]
    assert new_id != old_id

    old_lookup = await client.get(f"/api/v1/widget/{old_id}/config", headers={"Origin": ALLOWED_ORIGIN})
    assert old_lookup.status_code == 404

    new_lookup = await client.get(f"/api/v1/widget/{new_id}/config", headers={"Origin": ALLOWED_ORIGIN})
    assert new_lookup.status_code == 200


@pytest.mark.asyncio
async def test_widget_config_unknown_or_disabled_returns_404(client):
    response = await client.get(f"/api/v1/widget/wgt_{uuid4().hex}/config", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 404

    agent = await _create_agent(client)  # never enabled
    response = await client.get(f"/api/v1/widget/{agent['id']}/config", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_widget_config_requires_an_allowed_origin(client):
    agent = await _create_agent(client)
    enabled = await _enable_widget(client, agent["id"])
    public_id = enabled["widget_public_id"]

    no_origin = await client.get(f"/api/v1/widget/{public_id}/config")
    assert no_origin.status_code == 403

    wrong_origin = await client.get(
        f"/api/v1/widget/{public_id}/config", headers={"Origin": "https://evil.test"}
    )
    assert wrong_origin.status_code == 403

    ok = await client.get(f"/api/v1/widget/{public_id}/config", headers={"Origin": ALLOWED_ORIGIN})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    body = ok.json()["data"]
    assert body["name"] == agent["name"]
    assert body["greeting"] == agent["description"]


@pytest.mark.asyncio
async def test_empty_allowed_origins_denies_everyone_by_default(client):
    agent = await _create_agent(client)
    enabled = await _enable_widget(client, agent["id"], origins=[])
    public_id = enabled["widget_public_id"]

    response = await client.get(f"/api/v1/widget/{public_id}/config", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_widget_chat_rejects_a_disallowed_origin_before_touching_the_chat_pipeline(client):
    agent = await _create_agent(client)
    enabled = await _enable_widget(client, agent["id"])
    public_id = enabled["widget_public_id"]

    response = await client.post(
        f"/api/v1/widget/{public_id}/chat",
        json={"message": "Hello", "visitor_id": str(uuid4())},
        headers={"Origin": "https://evil.test"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_widget_chat_rejects_an_unknown_widget(client):
    response = await client.post(
        f"/api/v1/widget/wgt_{uuid4().hex}/chat",
        json={"message": "Hello", "visitor_id": str(uuid4())},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preflight_grants_cors_headers_only_for_an_allowed_origin(client):
    agent = await _create_agent(client)
    enabled = await _enable_widget(client, agent["id"])
    public_id = enabled["widget_public_id"]

    allowed = await client.options(f"/api/v1/widget/{public_id}/chat", headers={"Origin": ALLOWED_ORIGIN})
    assert allowed.status_code == 204
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in allowed.headers["access-control-allow-methods"]

    disallowed = await client.options(f"/api/v1/widget/{public_id}/chat", headers={"Origin": "https://evil.test"})
    assert disallowed.status_code == 204
    assert "access-control-allow-origin" not in disallowed.headers

    unknown = await client.options(f"/api/v1/widget/wgt_{uuid4().hex}/chat", headers={"Origin": ALLOWED_ORIGIN})
    assert unknown.status_code == 204
    assert "access-control-allow-origin" not in unknown.headers
