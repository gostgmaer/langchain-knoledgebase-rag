# Router health
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from packages.api.responses import ApiResponse
from packages.api.dependencies import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis
from packages.config.loader import settings

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Basic application health check with DB and Redis status.
    """
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    redis_status = "healthy"
    try:
        redis_client = Redis.from_url(
            str(settings.redis.url), encoding="utf-8", decode_responses=True
        )
        await redis_client.ping()
        await redis_client.aclose()
    except Exception:
        redis_status = "unhealthy"

    return ApiResponse(
        message="Health check successful.",
        data={
            "service": "EasyDev AI Platform",
            "version": "1.0.0",
            "status": (
                "healthy"
                if db_status == "healthy" and redis_status == "healthy"
                else "degraded"
            ),
            "database": db_status,
            "redis": redis_status,
        },
    )
