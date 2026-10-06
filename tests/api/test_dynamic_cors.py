"""
Real HTTP requests against the real FastAPI app (see tests/api/test_feature_flags_api.py's module
docstring for the shared `client` fixture's guarantees). Covers packages/api/middleware/cors.py's
`DynamicCORSMiddleware` — the piece docs/BUGS.md item 38 added so `cors_origins` can change
through Platform Settings without a restart, confirmed live against a genuine second-origin test
page while building the embeddable widget (item 37) that showed Starlette's own `CORSMiddleware`
answers every OPTIONS preflight itself from one list fixed at process startup.

Uses GET /api/v1/health — a public route (no auth needed), so these tests isolate CORS behaviour
from everything else a real route might fail on.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.api

DEFAULT_ORIGIN = "http://localhost:3000"


@pytest.mark.asyncio
async def test_default_allowed_origin_gets_the_cors_header(client):
    response = await client.get("/api/v1/health", headers={"Origin": DEFAULT_ORIGIN})
    assert response.headers.get("access-control-allow-origin") == DEFAULT_ORIGIN


@pytest.mark.asyncio
async def test_disallowed_origin_gets_no_cors_header(client):
    response = await client.get("/api/v1/health", headers={"Origin": "https://evil.test"})
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_preflight_on_an_ordinary_route_succeeds_for_an_allowed_origin(client):
    response = await client.options(
        "/api/v1/health",
        headers={"Origin": DEFAULT_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == DEFAULT_ORIGIN
    assert "GET" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_platform_settings_override_takes_effect_without_a_restart(client):
    custom_origin = "https://custom.example.com"

    # Before the override: the new origin is rejected, the default one still works.
    before = await client.get("/api/v1/health", headers={"Origin": custom_origin})
    assert "access-control-allow-origin" not in before.headers

    patched = await client.patch("/api/v1/platform-settings", json={"values": {"cors_origins": [custom_origin]}})
    assert patched.status_code == 200

    # After the override REPLACES the list (not merges): the new origin now works...
    after = await client.get("/api/v1/health", headers={"Origin": custom_origin})
    assert after.headers.get("access-control-allow-origin") == custom_origin

    # ...and the previously-default origin no longer does, proving this read the override.
    default_now_rejected = await client.get("/api/v1/health", headers={"Origin": DEFAULT_ORIGIN})
    assert "access-control-allow-origin" not in default_now_rejected.headers

    # Reverting restores the .env default.
    reverted = await client.patch("/api/v1/platform-settings", json={"values": {"cors_origins": None}})
    assert reverted.status_code == 200
    restored = await client.get("/api/v1/health", headers={"Origin": DEFAULT_ORIGIN})
    assert restored.headers.get("access-control-allow-origin") == DEFAULT_ORIGIN


@pytest.mark.asyncio
async def test_widget_paths_are_exempt_from_the_platform_wide_origin_list(client):
    """The widget router (docs/BUGS.md item 37) answers its own CORS entirely — a platform-wide
    override here must never leak into it, and an origin this middleware would reject must not be
    silently allowed through just because the path is exempt."""
    response = await client.get(
        "/api/v1/widget/wgt_does-not-exist/config", headers={"Origin": "https://evil.test"}
    )
    # Not 200 (the widget router's own origin check runs, and this origin isn't registered to any
    # agent) — critically, also not blocked/altered by DynamicCORSMiddleware's own header logic.
    assert "access-control-allow-origin" not in response.headers
    assert response.status_code in (403, 404)
