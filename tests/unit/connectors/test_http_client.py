from __future__ import annotations

import httpx
import pytest

from packages.connectors.http import (
    AuthenticationFailed,
    BlockedUrlError,
    HostCircuitOpen,
    ConnectorHttpError,
    assert_public_url,
)
from tests.unit.connectors.helpers import client


@pytest.mark.asyncio
async def test_a_transient_503_is_retried_with_backoff_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, text="ok")

    c = client(handler)
    response = await c.get("https://example.test/a")

    assert response.text == "ok"
    assert len(calls) == 3
    assert c.stats.retries == 2
    assert len(c.sleeps) == 2 and c.sleeps[1] > c.sleeps[0] * 0.9  # exponential


@pytest.mark.asyncio
async def test_429_honours_retry_after():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "7"}) if len(calls) == 1 else httpx.Response(200)

    c = client(handler)
    await c.get("https://example.test/a")

    assert c.sleeps == [7.0]
    assert c.stats.rate_limited == 1


@pytest.mark.asyncio
async def test_retry_after_is_capped():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "99999"}) if not handler.done else httpx.Response(200)

    handler.done = False
    c = client(lambda r: httpx.Response(429, headers={"Retry-After": "99999"}), max_retries=1)
    with pytest.raises(ConnectorHttpError):
        await c.get("https://example.test/a")
    assert max(c.sleeps) <= 60.0


@pytest.mark.asyncio
async def test_it_gives_up_after_max_retries_with_a_retryable_error():
    c = client(lambda r: httpx.Response(500), max_retries=2)
    with pytest.raises(ConnectorHttpError) as exc:
        await c.get("https://example.test/a")
    assert exc.value.retryable and exc.value.status == 500
    assert c.stats.requests == 3


@pytest.mark.asyncio
async def test_network_timeouts_are_retried_and_reported_without_the_query_string():
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)

    c = client(handler, max_retries=1)
    with pytest.raises(ConnectorHttpError) as exc:
        await c.get("https://example.test/a?token=SECRET")
    assert "SECRET" not in str(exc.value)
    assert c.stats.retries == 1


@pytest.mark.asyncio
async def test_the_circuit_opens_after_repeated_failures_and_recovers():
    now = [0.0]
    c = client(lambda r: httpx.Response(500), max_retries=0, breaker_threshold=3, breaker_cooldown=30, clock=lambda: now[0])
    for _ in range(3):
        with pytest.raises(ConnectorHttpError):
            await c.get("https://example.test/a")
    with pytest.raises(HostCircuitOpen):
        await c.get("https://example.test/a")
    assert c.stats.circuit_opened == 1

    now[0] = 31.0  # cool-down elapsed: one attempt is allowed through
    with pytest.raises(ConnectorHttpError) as exc:
        await c.get("https://example.test/a")
    assert not isinstance(exc.value, HostCircuitOpen)


@pytest.mark.asyncio
async def test_401_is_an_authentication_failure_not_a_generic_error():
    c = client(lambda r: httpx.Response(401))
    with pytest.raises(AuthenticationFailed):
        await c.get("https://example.test/a")


@pytest.mark.asyncio
async def test_a_crawler_client_can_treat_403_as_an_ordinary_page():
    c = client(lambda r: httpx.Response(403), raise_auth_errors=False)
    assert (await c.get("https://example.test/a")).status_code == 403


@pytest.mark.asyncio
async def test_rate_limit_headers_are_tracked_for_the_health_view():
    c = client(lambda r: httpx.Response(200, headers={"X-RateLimit-Remaining": "22", "X-RateLimit-Limit": "100"}))
    await c.get("https://example.test/a")
    assert c.stats.snapshot()["rate_limit_used_percent"] == 78


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8080/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ],
)
async def test_private_and_non_http_targets_are_blocked(url):
    with pytest.raises(BlockedUrlError):
        await assert_public_url(url)


@pytest.mark.asyncio
async def test_private_hosts_can_be_allowed_explicitly():
    await assert_public_url("http://10.0.0.5/", allow_private=True)
    with pytest.raises(BlockedUrlError):
        await assert_public_url("file:///etc/passwd", allow_private=True)  # the scheme rule always applies


@pytest.mark.asyncio
async def test_a_redirect_into_the_private_network_is_blocked():
    def handler(request):
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

    c = client(handler, allow_private=False)
    with pytest.raises(BlockedUrlError):
        # the first hop must be public for the request to start, so use a literal public address
        await c.get("http://93.184.216.34/start")


@pytest.mark.asyncio
async def test_credentials_are_not_forwarded_to_another_host_on_redirect():
    seen = []

    def handler(request):
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.example.test":
            return httpx.Response(302, headers={"Location": "https://files.example.test/blob"})
        return httpx.Response(200, text="data")

    c = client(handler)
    await c.get("https://api.example.test/item", headers={"Authorization": "Bearer SECRET"})

    assert seen[0] == ("api.example.test", "Bearer SECRET")
    assert seen[1] == ("files.example.test", None)


@pytest.mark.asyncio
async def test_too_many_redirects_fail():
    c = client(lambda r: httpx.Response(302, headers={"Location": "https://example.test/loop"}), max_redirects=3)
    with pytest.raises(ConnectorHttpError):
        await c.get("https://example.test/loop")


@pytest.mark.asyncio
async def test_requests_to_one_host_are_throttled():
    now = [0.0]
    c = client(lambda r: httpx.Response(200), min_interval=1.0, clock=lambda: now[0])
    await c.get("https://example.test/a")
    await c.get("https://example.test/b")
    assert c.sleeps and c.sleeps[0] == pytest.approx(1.0)
