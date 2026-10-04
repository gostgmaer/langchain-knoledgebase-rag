# Router users
from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import DEFAULT_TENANT_ID, get_scoped_container, require_uuid_header
from packages.api.responses import ApiResponse
from packages.api.schemas.user import UserListResponseSchema, UserResponseSchema
from packages.api.security import get_bearer_token
from packages.infrastructure.container import ApplicationContainer
from packages.sdk.common.exceptions import NotFoundException, SDKException
from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[UserResponseSchema],
    summary="Resolve a user's real name",
    description=(
        "Proxies to IAM's GET /users/:id — IAM is the system of record for identity; this app "
        "only ever stores a user_id (e.g. Document.uploaded_by), never a name. No special "
        "permission beyond authentication: the caller must already know the id, this only "
        "resolves what it displays as."
    ),
)
async def get_user(
    user_id: UUID,
    container: ApplicationContainer = Depends(get_scoped_container),
    access_token: str | None = Depends(get_bearer_token),
):
    iam_client = container.iam.client()

    try:
        user = await iam_client.users.get_user(str(user_id), access_token=access_token)
    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such user.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("IAM service unreachable resolving user %s: %s", user_id, exc)
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
        message="User retrieved.",
        data=UserResponseSchema(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            is_active=user.is_active,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[UserListResponseSchema],
    summary="List the calling tenant's real members",
    description=(
        "Proxies to IAM's GET /users?tenantId=... — the tenant's real members (docs/BUGS.md item "
        "32), not just pending invitations. No separate permission check here: IAM enforces its "
        "own (user:read_all), and silently scopes a non-super-admin caller to their own tenant "
        "regardless of the X-Tenant-ID this app resolves."
    ),
)
async def list_users(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    container: ApplicationContainer = Depends(get_scoped_container),
    access_token: str | None = Depends(get_bearer_token),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    iam_client = container.iam.client()

    try:
        users = await iam_client.users.list_users(str(tenant_id), access_token=access_token, limit=limit)
    except httpx.HTTPError as exc:
        logger.error("IAM service unreachable listing users for tenant %s: %s", tenant_id, exc)
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
        message="Users retrieved.",
        data=UserListResponseSchema(
            users=[
                UserResponseSchema(
                    id=u.id,
                    email=u.email,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    display_name=u.display_name,
                    is_active=u.is_active,
                )
                for u in users
            ],
        ),
    )
