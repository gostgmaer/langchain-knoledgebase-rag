import asyncio

import pytest

from packages.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


def test_starts_closed():
    breaker = CircuitBreaker(name="test", failure_threshold=3)
    assert breaker.state is CircuitState.CLOSED
    breaker.check()  # should not raise


def test_opens_after_failure_threshold_is_reached():
    breaker = CircuitBreaker(name="test", failure_threshold=3)

    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED

    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN


def test_open_breaker_fails_fast_on_check():
    breaker = CircuitBreaker(name="test", failure_threshold=1)
    breaker.record_failure()

    with pytest.raises(CircuitBreakerOpenError):
        breaker.check()


def test_success_resets_failure_count_and_closes():
    breaker = CircuitBreaker(name="test", failure_threshold=2)

    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()

    # Would have opened on this 2nd consecutive failure had the success
    # above not reset the count back to 0.
    assert breaker.state is CircuitState.CLOSED


def test_transitions_to_half_open_after_reset_timeout():
    breaker = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.05)
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN

    import time

    time.sleep(0.1)

    assert breaker.state is CircuitState.HALF_OPEN


def test_half_open_failure_reopens_immediately():
    breaker = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.05)
    breaker.record_failure()

    import time

    time.sleep(0.1)
    assert breaker.state is CircuitState.HALF_OPEN

    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN


@pytest.mark.asyncio
async def test_call_wraps_success_and_failure_correctly():
    breaker = CircuitBreaker(name="test", failure_threshold=1)

    async def ok() -> str:
        return "result"

    assert await breaker.call(ok) == "result"
    assert breaker.state is CircuitState.CLOSED

    async def fails() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await breaker.call(fails)

    assert breaker.state is CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(ok)


@pytest.mark.asyncio
async def test_call_does_not_swallow_the_original_exception():
    breaker = CircuitBreaker(name="test", failure_threshold=5)

    async def fails() -> None:
        raise ValueError("specific failure")

    with pytest.raises(ValueError, match="specific failure"):
        await breaker.call(fails)


@pytest.mark.asyncio
async def test_concurrent_calls_do_not_corrupt_failure_count():
    breaker = CircuitBreaker(name="test", failure_threshold=100)

    async def fails() -> None:
        raise RuntimeError("boom")

    results = await asyncio.gather(
        *(breaker.call(fails) for _ in range(10)),
        return_exceptions=True,
    )

    assert all(isinstance(r, RuntimeError) for r in results)
    assert breaker._failure_count == 10
