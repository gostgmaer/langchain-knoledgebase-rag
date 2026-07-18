# Router health
from __future__ import annotations

from fastapi import APIRouter, Request
from packages.api.responses import ApiResponse

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

    return ApiResponse(
        message="Health check successful.",
        data={
            "service": "EasyDev AI Platform",
            "version": "1.0.0",
            "status": "healthy",
        }
    )
