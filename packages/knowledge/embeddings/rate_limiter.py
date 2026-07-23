"""
Self-imposed embedding rate limiter.

Added after a backlog of queued ingestion jobs all fired their embedding
calls at once and blew through Gemini's free-tier quota (100 requests/min
for gemini-embedding-1.0), failing every one of them with a 429. This caps
outgoing calls below whatever the provider enforces server-side, so this
app runs out of *its own* budget with a clean, bounded wait instead of a
provider-side rejection.

Scoped to one process: EmbeddingManager (packages/knowledge/embeddings/
manager.py) is a DI Singleton per ApplicationContainer, and each arq
worker process holds its own container (packages/worker/main.py), so one
limiter instance correctly caps every job running concurrently within
that worker — arq's own `concurrency` setting is exactly the fan-out this
guards against. Running multiple worker processes would need a shared
(e.g. Redis-backed) limiter instead; out of scope for the single local
worker this app runs today.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

import tiktoken

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


class EmbeddingRateLimiter:
    """Sliding-window cap on requests and tokens over a rolling window."""

    def __init__(
        self,
        max_requests: int,
        max_tokens: int,
        window_seconds: float = 60.0,
    ) -> None:
        self._max_requests = max_requests
        self._max_tokens = max_tokens
        self._window_seconds = window_seconds
        self._request_times: deque[float] = deque()
        self._token_events: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    @staticmethod
    def count_tokens(texts: list[str]) -> int:
        return sum(len(_TOKENIZER.encode(text)) for text in texts)

    async def acquire(self, token_count: int) -> None:
        """Blocks until there's budget for one more call costing `token_count` tokens."""
        while True:
            async with self._lock:
                now = time.monotonic()
                self._evict(now)

                token_total = sum(count for _, count in self._token_events)
                requests_ok = len(self._request_times) < self._max_requests
                tokens_ok = token_total + token_count <= self._max_tokens

                if requests_ok and tokens_ok:
                    self._request_times.append(now)
                    self._token_events.append((now, token_count))
                    return

                wait_seconds = self._time_until_capacity(now, token_count, token_total)

            await asyncio.sleep(max(wait_seconds, 0.1))

    def _evict(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._request_times and self._request_times[0] <= cutoff:
            self._request_times.popleft()
        while self._token_events and self._token_events[0][0] <= cutoff:
            self._token_events.popleft()

    def _time_until_capacity(self, now: float, token_count: int, token_total: int) -> float:
        candidates: list[float] = []

        if len(self._request_times) >= self._max_requests:
            candidates.append(self._request_times[0] + self._window_seconds - now)

        if token_total + token_count > self._max_tokens:
            running = token_total
            for event_time, count in self._token_events:
                running -= count
                if running + token_count <= self._max_tokens:
                    candidates.append(event_time + self._window_seconds - now)
                    break
            else:
                # A single call requesting more tokens than the whole
                # budget can ever hold — the window itself is the only
                # bound available; it will still be rejected by the
                # provider, but not immediately hammered in a tight loop.
                candidates.append(self._window_seconds)

        return max(candidates) if candidates else 0.0
