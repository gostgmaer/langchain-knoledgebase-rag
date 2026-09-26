"""
The one HTTP client every connector uses, so throttling, retry, backoff, 429/Retry-After handling,
timeouts, circuit breaking and SSRF protection are written once and cannot be forgotten by a connector.
"""

from __future__ import annotations

import asyncio
import ipaddress
import random
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from packages.shared.logging import get_logger

logger = get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
REDIRECT_STATUS = {301, 302, 303, 307, 308}
MAX_RETRY_AFTER_SECONDS = 60.0


class ConnectorHttpError(Exception):
    """A request could not be completed (after retries). Never carries credentials."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class BlockedUrlError(ConnectorHttpError):
    """The URL points somewhere a connector must never call (private network, bad scheme...)."""


class HostCircuitOpen(ConnectorHttpError):
    """The host failed repeatedly and is being left alone for a cool-down."""


class AuthenticationFailed(ConnectorHttpError):
    """The credentials were rejected (401/403)."""


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


async def assert_public_url(url: str, *, allow_private: bool = False) -> None:
    """
    Refuses anything but http(s) to a public address, so a source URL can never be used to reach
    the platform's own network, cloud metadata endpoints or loopback (server-side request forgery).
    `allow_private` (CONNECTOR_ALLOW_PRIVATE_HOSTS) is for self-hosted systems on a private network.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise BlockedUrlError(f"Only http and https URLs are allowed (got '{parts.scheme or 'none'}').")
    host = parts.hostname
    if not host:
        raise BlockedUrlError("The URL has no host.")
    if allow_private:
        return

    try:
        addresses = [host] if _looks_like_ip(host) else await _resolve(host, parts.port)
    except OSError as exc:
        raise BlockedUrlError(f"Could not resolve '{host}'.") from exc
    for address in addresses:
        if not _is_public_address(address):
            raise BlockedUrlError(
                f"'{host}' resolves to a non-public address; set CONNECTOR_ALLOW_PRIVATE_HOSTS only for "
                "systems that legitimately live on a private network."
            )


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


async def _resolve(host: str, port: int | None) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


@dataclass
class HttpStats:
    requests: int = 0
    retries: int = 0
    errors: int = 0
    rate_limited: int = 0
    circuit_opened: int = 0
    last_status: int | None = None
    last_error: str | None = None
    rate_limit_remaining: int | None = None
    rate_limit_limit: int | None = None
    total_seconds: float = 0.0

    def snapshot(self) -> dict[str, Any]:
        used = None
        if self.rate_limit_limit and self.rate_limit_remaining is not None:
            used = round(100 * (1 - self.rate_limit_remaining / self.rate_limit_limit))
        return {
            "requests": self.requests,
            "retries": self.retries,
            "errors": self.errors,
            "rate_limited": self.rate_limited,
            "circuit_opened": self.circuit_opened,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "rate_limit_remaining": self.rate_limit_remaining,
            "rate_limit_used_percent": used,
            "avg_latency_ms": round(1000 * self.total_seconds / self.requests) if self.requests else None,
        }


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float | None = None


@dataclass
class ResilientHttpClient:
    """
    Throttled, retrying, circuit-broken, SSRF-safe HTTP client.

    * `min_interval`: minimum seconds between requests to the same host (politeness / API quotas).
    * `max_concurrency`: simultaneous in-flight requests.
    * retries: network errors, timeouts and 429/5xx, exponential backoff with jitter; `Retry-After`
      is honoured (capped at MAX_RETRY_AFTER_SECONDS).
    * circuit breaker: `breaker_threshold` consecutive failures open a host for `breaker_cooldown` seconds.
    * redirects are followed manually so every hop is checked against the URL policy.
    """

    headers: dict[str, str] = field(default_factory=dict)
    auth: httpx.Auth | tuple[str, str] | None = None
    timeout: float = 20.0
    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 20.0
    min_interval: float = 0.0
    max_concurrency: int = 4
    max_redirects: int = 5
    max_response_bytes: int = 15 * 1024 * 1024
    breaker_threshold: int = 5
    breaker_cooldown: float = 30.0
    allow_private: bool = False
    raise_auth_errors: bool = True
    """API connectors want 401/403 as AuthenticationFailed; a crawler treats them as ordinary pages."""
    transport: httpx.AsyncBaseTransport | None = None
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    clock: Callable[[], float] = time.monotonic
    stats: HttpStats = field(default_factory=HttpStats)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers=self.headers,
            auth=self.auth,
            timeout=self.timeout,
            follow_redirects=False,
            transport=self.transport,
        )
        self._semaphore = asyncio.Semaphore(max(1, self.max_concurrency))
        self._last_request_at: dict[str, float] = {}
        self._throttle_lock = asyncio.Lock()
        self._breakers: dict[str, _Breaker] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ public

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Returns the final response of a successful request; raises ConnectorHttpError otherwise."""
        started = self.clock()
        try:
            return await self._with_redirects(method, url, **kwargs)
        finally:
            self.stats.total_seconds += self.clock() - started

    # ------------------------------------------------------------------ internals

    async def _with_redirects(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        current = url
        for _hop in range(self.max_redirects + 1):
            response = await self._send_with_retries(method, current, **dict(kwargs))
            if response.status_code in REDIRECT_STATUS and (location := response.headers.get("location")):
                target = urljoin(current, location)
                if urlsplit(target).netloc != urlsplit(current).netloc:
                    # Never forward credentials to a different host (e.g. a pre-signed download URL).
                    kwargs = _without_credentials(kwargs)
                current = target
                if response.status_code == 303:
                    method = "GET"
                continue
            return response
        raise ConnectorHttpError(f"Too many redirects starting at {_safe(url)}.")

    async def _send_with_retries(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        host = urlsplit(url).netloc
        await assert_public_url(url, allow_private=self.allow_private)
        raise_auth = kwargs.pop("raise_auth_errors", self.raise_auth_errors)

        attempt = 0
        while True:
            self._check_breaker(host)
            try:
                response = await self._send_once(method, url, host, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                self._record_failure(host, f"{type(exc).__name__}")
                if attempt >= self.max_retries:
                    raise ConnectorHttpError(
                        f"{type(exc).__name__} calling {_safe(url)} (gave up after {attempt + 1} attempts).",
                        retryable=True,
                    ) from exc
                await self._backoff(attempt, None)
                attempt += 1
                self.stats.retries += 1
                continue

            self.stats.last_status = response.status_code
            self._read_rate_limit(response)

            if response.status_code in RETRYABLE_STATUS:
                if response.status_code == 429:
                    self.stats.rate_limited += 1
                self._record_failure(host, f"HTTP {response.status_code}")
                if attempt >= self.max_retries:
                    raise ConnectorHttpError(
                        f"HTTP {response.status_code} from {_safe(url)} (gave up after {attempt + 1} attempts).",
                        status=response.status_code,
                        retryable=True,
                    )
                await self._backoff(attempt, response.headers.get("retry-after"))
                attempt += 1
                self.stats.retries += 1
                continue

            self._record_success(host)
            if raise_auth and response.status_code in (401, 403):
                # Surfaced as its own type so a sync can mark the source "disconnected" rather than "error".
                self.stats.errors += 1
                self.stats.last_error = f"HTTP {response.status_code}"
                raise AuthenticationFailed(
                    f"HTTP {response.status_code} from {_safe(url)}: the credentials were rejected or lack access.",
                    status=response.status_code,
                )
            return response

    async def _send_once(self, method: str, url: str, host: str, **kwargs: Any) -> httpx.Response:
        async with self._semaphore:
            await self._throttle(host)
            self.stats.requests += 1
            response = await self._client.request(method, url, **kwargs)
            if len(response.content) > self.max_response_bytes:
                raise ConnectorHttpError(f"Response from {_safe(url)} is larger than the allowed size.")
            return response

    async def _throttle(self, host: str) -> None:
        if self.min_interval <= 0:
            return
        async with self._throttle_lock:
            now = self.clock()
            wait = self._last_request_at.get(host, 0.0) + self.min_interval - now
            if wait > 0:
                await self.sleep(wait)
            self._last_request_at[host] = self.clock()

    async def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay = _parse_retry_after(retry_after)
        if delay is None:
            delay = min(self.backoff_max, self.backoff_base * (2**attempt))
            delay += random.uniform(0, delay / 4)
        await self.sleep(min(delay, MAX_RETRY_AFTER_SECONDS))

    # --- circuit breaker

    def _check_breaker(self, host: str) -> None:
        breaker = self._breakers.get(host)
        if breaker and breaker.opened_at is not None:
            if self.clock() - breaker.opened_at < self.breaker_cooldown:
                raise HostCircuitOpen(f"Too many recent failures calling {host}; pausing before trying again.", retryable=True)
            breaker.opened_at = None  # half-open: let one attempt through
            breaker.failures = self.breaker_threshold - 1

    def _record_failure(self, host: str, reason: str) -> None:
        self.stats.errors += 1
        self.stats.last_error = reason
        breaker = self._breakers.setdefault(host, _Breaker())
        breaker.failures += 1
        if breaker.failures >= self.breaker_threshold and breaker.opened_at is None:
            breaker.opened_at = self.clock()
            self.stats.circuit_opened += 1
            logger.warning("Connector circuit opened", host=host, reason=reason)

    def _record_success(self, host: str) -> None:
        breaker = self._breakers.get(host)
        if breaker:
            breaker.failures = 0
            breaker.opened_at = None

    def _read_rate_limit(self, response: httpx.Response) -> None:
        for remaining_header, limit_header in (
            ("x-ratelimit-remaining", "x-ratelimit-limit"),
            ("ratelimit-remaining", "ratelimit-limit"),
            ("x-rate-limit-remaining", "x-rate-limit-limit"),
        ):
            remaining = response.headers.get(remaining_header)
            if remaining and remaining.isdigit():
                self.stats.rate_limit_remaining = int(remaining)
                limit = response.headers.get(limit_header)
                self.stats.rate_limit_limit = int(limit) if limit and limit.isdigit() else self.stats.rate_limit_limit
                return


def _without_credentials(kwargs: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(kwargs)
    cleaned.pop("auth", None)
    if cleaned.get("headers"):
        cleaned["headers"] = {k: v for k, v in cleaned["headers"].items() if k.lower() not in ("authorization", "cookie")}
    return cleaned


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def _safe(url: str) -> str:
    """The URL without its query string or credentials, for messages and logs."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname or ''}{parts.path}"
