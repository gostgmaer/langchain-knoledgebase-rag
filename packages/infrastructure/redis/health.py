from redis.asyncio import Redis


async def redis_health(
    client: Redis,
) -> bool:
    try:
        await client.ping()
        return True
    except Exception:
        return False