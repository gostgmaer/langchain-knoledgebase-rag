from __future__ import annotations

from collections.abc import Callable

import httpx

from packages.connectors.http import ResilientHttpClient
from packages.connectors.models import DiscoveryContext
from uuid import uuid4


def client(handler: Callable[[httpx.Request], httpx.Response], **kwargs) -> ResilientHttpClient:
    """A resilient client over an in-memory transport: no network, no real sleeping."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    kwargs.setdefault("allow_private", True)
    kwargs.setdefault("min_interval", 0.0)
    kwargs.setdefault("raise_auth_errors", True)
    c = ResilientHttpClient(transport=httpx.MockTransport(handler), sleep=fake_sleep, **kwargs)
    c.sleeps = sleeps  # type: ignore[attr-defined]
    return c


def context(**kwargs) -> DiscoveryContext:
    return DiscoveryContext(source_id=uuid4(), tenant_id=uuid4(), **kwargs)


async def collect(agen) -> list:
    return [item async for item in agen]
