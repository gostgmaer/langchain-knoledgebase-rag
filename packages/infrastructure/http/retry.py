from __future__ import annotations

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from packages.config.loader import settings
from packages.infrastructure.resilience.circuit_breaker import CircuitBreaker
from packages.shared.logging import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class RetryTransport(httpx.AsyncBaseTransport):
    """
    Wraps another async transport, retrying transient failures
    (connection errors, timeouts, 5xx responses) with exponential
    backoff — Production hardening's own "Retry policies" gap.
    `tenacity` was already a declared dependency with nothing using it;
    `packages/config/queue.py`'s `max_retries`/`retry_delay` were also
    already there, just never read by anything HTTP-related. This is
    what finally reads them.

    Applied at the transport layer (via `create_http_client()`) rather
    than call-site-by-call-site so every consumer of the shared client
    factory (currently IAM and Upload SDK clients) gets it for free.

    Also wraps each destination host in its own `CircuitBreaker`: once a
    host has failed `settings.queue.max_retries`-exhausted requests
    `circuit_breaker_failure_threshold` times in a row, further requests
    to that host fail immediately instead of each paying a full
    retry-then-timeout cycle against something that's clearly down. One
    breaker failure is recorded per *outer* request (after its own
    retries are exhausted), not per individual retry attempt.
    """

    def __init__(
        self,
        wrapped: httpx.AsyncBaseTransport,
        breaker_failure_threshold: int = 5,
        breaker_reset_timeout_seconds: float = 30.0,
    ) -> None:
        self._wrapped = wrapped
        self._breaker_failure_threshold = breaker_failure_threshold
        self._breaker_reset_timeout_seconds = breaker_reset_timeout_seconds
        self._breakers: dict[str, CircuitBreaker] = {}

    def _breaker_for(self, host: str | None) -> CircuitBreaker:
        key = host or "unknown"

        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(
                name=f"http:{key}",
                failure_threshold=self._breaker_failure_threshold,
                reset_timeout_seconds=self._breaker_reset_timeout_seconds,
            )

        return self._breakers[key]

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        breaker = self._breaker_for(request.url.host)

        async def _do_request() -> httpx.Response:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.queue.max_retries),
                wait=wait_exponential(
                    multiplier=settings.queue.retry_delay,
                    max=30,
                ),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    response = await self._wrapped.handle_async_request(request)

                    if response.status_code >= 500:
                        await response.aread()
                        raise httpx.HTTPStatusError(
                            f"Server error {response.status_code}",
                            request=request,
                            response=response,
                        )

                    if attempt.retry_state.attempt_number > 1:
                        logger.info(
                            "HTTP request succeeded after retry",
                            url=str(request.url),
                            attempt=attempt.retry_state.attempt_number,
                        )

                    return response

            # Unreachable: AsyncRetrying either returns from inside `with attempt`
            # or re-raises (reraise=True) once attempts are exhausted.
            raise RuntimeError("retry loop exited without a response")

        return await breaker.call(_do_request)

    async def aclose(self) -> None:
        await self._wrapped.aclose()
