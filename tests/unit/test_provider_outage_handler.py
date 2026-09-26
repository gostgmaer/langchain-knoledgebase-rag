from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.api.exception_handlers import register_exception_handlers


def _fake_error(module: str, name: str, **attrs):
    """An exception that looks like a provider SDK's (same module and class name)."""
    err = type(name, (Exception,), {"__module__": module})("upstream said no")
    for key, value in attrs.items():
        setattr(err, key, value)
    return err


def _client(exc: Exception) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def test_gemini_overload_becomes_a_503_with_retry_after():
    resp = _client(_fake_error("google.genai.errors", "ServerError", code=503)).get("/boom")

    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "30"
    body = resp.json()
    assert body["error"] == "ProviderUnavailable"
    assert "try again" in body["message"].lower()
    # No provider internals leak to the client.
    assert "upstream said no" not in resp.text


def test_openai_rate_limit_is_also_reported_as_unavailable():
    resp = _client(_fake_error("openai", "RateLimitError", status_code=429)).get("/boom")

    assert resp.status_code == 503


def test_an_ordinary_bug_is_still_a_500():
    resp = _client(ValueError("real bug")).get("/boom")

    assert resp.status_code == 500
    assert resp.json()["error"] == "InternalServerError"


def test_a_provider_client_error_is_not_masked_as_an_outage():
    # A 400 from the provider is our bug (bad request), not the provider being down.
    resp = _client(_fake_error("google.genai.errors", "ClientError", code=400)).get("/boom")

    assert resp.status_code == 500


def test_a_cyclic_exception_group_does_not_recurse_forever():
    from packages.api.exception_handlers import _is_provider_outage

    inner = ValueError("inner")
    group = ExceptionGroup("group", [inner])
    inner.__context__ = group  # the cycle seen in production (task group and its member)

    assert _is_provider_outage(group) is False


def test_a_connector_circuit_is_not_mistaken_for_an_ai_provider_outage():
    from packages.api.exception_handlers import _is_provider_outage
    from packages.connectors.http import HostCircuitOpen

    assert _is_provider_outage(HostCircuitOpen("paused")) is False
