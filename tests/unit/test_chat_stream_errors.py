from __future__ import annotations

import json

import pytest

from packages.api.routers.chat import _sse_events


def _fake_error(module: str, name: str, **attrs):
    err = type(name, (Exception,), {"__module__": module})("internal detail")
    for key, value in attrs.items():
        setattr(err, key, value)
    return err


class _FailingService:
    """Streams two tokens, then the provider fails."""

    def __init__(self, error):
        self._error = error

    async def stream(self, _request):
        yield {"type": "token", "content": "Hel"}
        yield {"type": "token", "content": "lo"}
        raise self._error


async def _collect(service):
    events = []
    async for chunk in _sse_events(service, None, "conv-1", None, None, None, None, ""):
        assert chunk.startswith("data: ") and chunk.endswith("\n\n")
        events.append(json.loads(chunk[len("data: "):]))
    return events


@pytest.mark.asyncio
async def test_a_provider_outage_mid_answer_ends_with_a_retryable_error_event():
    events = await _collect(_FailingService(_fake_error("google.genai.errors", "ServerError", code=503)))

    assert [e["type"] for e in events] == ["token", "token", "error"]
    assert events[-1]["retryable"] is True
    assert "try again" in events[-1]["message"].lower()
    assert "internal detail" not in json.dumps(events)


@pytest.mark.asyncio
async def test_any_other_failure_is_reported_without_leaking_internals():
    events = await _collect(_FailingService(ValueError("internal detail")))

    assert events[-1]["type"] == "error"
    assert events[-1]["retryable"] is False
    assert "internal detail" not in json.dumps(events)
    # No misleading "done" after a failure.
    assert all(e["type"] != "done" for e in events)
