from __future__ import annotations

from redis.asyncio import Redis

from packages.config.redis import RedisSettings


def create_redis_client(
    settings: RedisSettings,
) -> Redis:
    """Create Redis client."""

    return Redis.from_url(
        str(settings.url),
        encoding="utf-8",
        decode_responses=True,
    )