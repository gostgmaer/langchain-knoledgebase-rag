# Router tenants
from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from packages.api.dependencies import get_scoped_container
from packages.api.responses import ApiResponse
from packages.api.schemas.tenant import TenantResponseSchema
from packages.api.security import get_bearer_token
from packages.infrastructure.container import ApplicationContainer
from packages.sdk.common.exceptions import NotFoundException, SDKException
from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"],
)


@router.get(
    "/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TenantResponseSchema],
    summary="Resolve a tenant's real name",
    description=(
        "Proxies to IAM's GET /tenants/:id — IAM is the system of record for "
        "organizations; this app only ever stores a tenant_id, never a name. "
        "No special permission beyond authentication: the caller must already "
        "know the id (their own token's tenant, or one they're deliberately "
        "browsing as), this only resolves what it displays as."
    ),
)
async def get_tenant(
    tenant_id: UUID,
    container: ApplicationContainer = Depends(get_scoped_container),
    access_token: str | None = Depends(get_bearer_token),
):
    iam_client = container.iam.client()

    try:
        tenant = await iam_client.tenants.get_tenant(str(tenant_id), access_token=access_token)
    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such tenant.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("IAM service unreachable resolving tenant %s: %s", tenant_id, exc)
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
        message="Tenant retrieved.",
        data=TenantResponseSchema(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
        ),
    )
