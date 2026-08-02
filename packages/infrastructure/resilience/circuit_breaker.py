from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

from packages.shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is rejected because its circuit is open."""


class CircuitBreaker:
    """
    Minimal async-friendly circuit breaker: after `failure_threshold`
    consecutive failures, further calls fail immediately (OPEN) instead
    of retrying against a provider that's clearly down. After
    `reset_timeout_seconds`, one call is let through as a probe
    (HALF_OPEN) — success closes the breaker, failure re-opens it.

    In-memory, per-process state only — matches this app's existing
    idiom for resilience state (see packages/api/middleware/metrics.py,
    rate_limit.py), not shared across replicas.

    `check()`/`record_success()`/`record_failure()` are exposed
    separately from `call()` so streaming call sites (async generators,
    which can't be wrapped in a single awaitable) can manage the
    try/except themselves around the iteration.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 30.0,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._reset_timeout_seconds
        ):
            self._state = CircuitState.HALF_OPEN

        return self._state

    def check(self) -> None:
        if self.state is CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit '{self._name}' is open — failing fast instead of "
                "calling a provider that's clearly down."
            )

    def record_success(self) -> None:
        if self._state is not CircuitState.CLOSED:
            logger.info("Circuit closed", name=self._name)

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failure_count += 1

        if self._state is CircuitState.HALF_OPEN or self._failure_count >= self._failure_threshold:
            if self._state is not CircuitState.OPEN:
                logger.warning(
                    "Circuit opened",
                    name=self._name,
                    failure_count=self._failure_count,
                )
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        self.check()

        try:
            result = await fn()
        except Exception:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result
