# Router api keys
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_current_user,
    get_scoped_container,
    require_admin,
    require_permission,
    require_uuid_header,
)
from packages.api.permissions import Permission
from packages.api.responses import ApiResponse
from packages.api.schemas.api_key import (
    ApiKeyListResponseSchema,
    ApiKeyResponseSchema,
    CreateApiKeyRequestSchema,
    CreateApiKeyResponseSchema,
)
from packages.auth.api_keys import generate_api_key
from packages.domain.models.api_key import ApiKey
from packages.infrastructure.container import ApplicationContainer
from packages.sdk.iam.models import CurrentUser

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"],
    dependencies=[Depends(require_admin())],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[CreateApiKeyResponseSchema],
    dependencies=[Depends(require_permission(Permission.API_KEYS_WRITE))],
    summary="Mint a new API key",
    description=(
        "Creates a new tenant-scoped API key for programmatic access to this API "
        "(docs/BUGS.md item 33) — send it as `Authorization: Bearer <key>` instead of an "
        "IAM-issued token. The real key is returned exactly once, in this response; only its "
        "hash is ever stored, so losing it means creating a new one, not recovering this one. "
        "It acts with full admin-equivalent access to this tenant, attributed back to whoever "
        "created it for audit purposes."
    ),
)
async def create_api_key(
    payload: CreateApiKeyRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
    current_user: CurrentUser | None = Depends(get_current_user),
):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A real, authenticated session is required to create an API key.",
        )

    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    api_keys = container.repositories.api_key()

    raw_key, key_prefix, key_hash = generate_api_key()

    key = ApiKey(
        tenant_id=tenant_id,
        name=payload.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        created_by_user_id=current_user.id,
        created_by_email=current_user.email,
        expires_at=payload.expires_at,
        is_active=True,
    )

    created = await api_keys.create(key)

    return ApiResponse(
        message="API key created — this is the only time the real key is shown.",
        data=CreateApiKeyResponseSchema(
            id=created.id,
            name=created.name,
            key=raw_key,
            key_prefix=created.key_prefix,
            expires_at=created.expires_at,
            created_at=created.created_at,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ApiKeyListResponseSchema],
    dependencies=[Depends(require_permission(Permission.API_KEYS_READ))],
    summary="List API keys",
    description="This tenant's API keys, active or revoked — never the real key or its hash.",
)
async def list_api_keys(
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    api_keys = container.repositories.api_key()

    rows = await api_keys.list_by_tenant(tenant_id)

    return ApiResponse(
        message="API keys retrieved.",
        data=ApiKeyListResponseSchema(api_keys=[ApiKeyResponseSchema.model_validate(k) for k in rows]),
    )


@router.delete(
    "/{api_key_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ApiKeyResponseSchema],
    dependencies=[Depends(require_permission(Permission.API_KEYS_WRITE))],
    summary="Revoke an API key",
    description=(
        "Immediately stops the key from authenticating anything further. Not a hard delete — "
        "the row stays, marked revoked, so it's still visible in the list for audit purposes."
    ),
)
async def revoke_api_key(
    api_key_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    api_keys = container.repositories.api_key()

    key = await api_keys.get(api_key_id)
    if key is None or key.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )

    revoked = await api_keys.revoke(key)

    return ApiResponse(
        message="API key revoked.",
        data=ApiKeyResponseSchema.model_validate(revoked),
    )
