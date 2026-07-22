# Router auth
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from packages.api.dependencies import get_scoped_container
from packages.api.responses import ApiResponse
from packages.api.schemas.auth import (
    RefreshTokenRequestSchema,
    RefreshTokenResponseSchema,
)
from packages.infrastructure.container import ApplicationContainer
from packages.sdk.common.exceptions import SDKException, UnauthorizedException
from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[RefreshTokenResponseSchema],
    summary="Refresh an access token",
    description=(
        "Proxies to the IAM service's own POST /auth/refresh — lets "
        "callers of this API refresh a session without talking to IAM "
        "directly. Requires a real refresh token issued by IAM at login; "
        "this app doesn't issue its own sessions."
    ),
)
async def refresh(
    payload: RefreshTokenRequestSchema,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    iam_client = container.iam.client()

    try:
        refreshed = await iam_client.auth.refresh_token(payload.refresh_token)
    except UnauthorizedException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("IAM service unreachable during refresh: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the IAM service.",
        ) from exc
    except SDKException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ApiResponse(
        message="Token refreshed.",
        data=RefreshTokenResponseSchema(
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token,
            token_type=refreshed.token_type,
            expires_in=refreshed.expires_in,
        ),
    )
