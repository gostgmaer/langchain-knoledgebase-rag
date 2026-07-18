# Router health
from __future__ import annotations

from fastapi import APIRouter, Request

from packages.api.responses import success

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health(
    request: Request,
):
    """
    Basic application health check.
    """

    return success(
        message="Application is healthy.",
        data={
            "service": "EasyDev AI Platform",
            "version": "1.0.0",
            "status": "healthy",
        },
    )