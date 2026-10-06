# Router platform settings
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_admin,
    require_permission,
    require_uuid_header,
)
from packages.api.permissions import Permission
from packages.api.responses import ApiResponse
from packages.api.schemas.platform_settings import (
    PlatformSettingItemSchema,
    PlatformSettingsResponseSchema,
    PlatformSettingsUpdateSchema,
)
from packages.application.services.platform_settings_service import SETTINGS, PlatformSettingsService
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/platform-settings",
    tags=["Platform Settings"],
    dependencies=[Depends(require_admin())],
)


async def _response(service: PlatformSettingsService) -> PlatformSettingsResponseSchema:
    items = []
    for spec in SETTINGS:
        value = await service.get(spec.key)
        env_default = spec.env_default()
        items.append(
            PlatformSettingItemSchema(
                key=spec.key,
                label=spec.label,
                kind=spec.kind,
                help=spec.help,
                minimum=spec.minimum,
                maximum=spec.maximum,
                value=value,
                env_default=env_default,
                is_overridden=value != env_default,
            )
        )
    return PlatformSettingsResponseSchema(settings=items)


@router.get(
    "",
    response_model=ApiResponse[PlatformSettingsResponseSchema],
    dependencies=[Depends(require_permission(Permission.PLATFORM_SETTINGS_READ))],
    summary="Platform operational settings",
    description=(
        "Every operational knob an admin can change without a redeploy — rate limits, CORS "
        "origins, retention windows — each with its current effective value, the `.env` default, "
        "and whether it's currently overridden. Secrets and security-boundary settings (API keys, "
        "AUTH_REQUIRED, admin roles) are never listed here; they stay `.env`-only."
    ),
)
async def get_platform_settings(
    container: ApplicationContainer = Depends(get_scoped_container),
):
    service = container.platform_settings.service()
    return ApiResponse(message="Platform settings retrieved.", data=await _response(service))


@router.patch(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PlatformSettingsResponseSchema],
    dependencies=[Depends(require_permission(Permission.PLATFORM_SETTINGS_WRITE))],
    summary="Change one or more platform settings",
    description=(
        "Partial update, keyed by setting key. A key mapped to `null` reverts that setting to its "
        "`.env` default. Takes effect within about 30 seconds (the service's in-process cache TTL) "
        "and is audited."
    ),
)
async def update_platform_settings(
    payload: PlatformSettingsUpdateSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)
    service = container.platform_settings.service()

    specs = {spec.key: spec for spec in SETTINGS}
    errors: list[str] = []
    for key, value in payload.values.items():
        spec = specs.get(key)
        if spec is None:
            errors.append(f"Unknown setting '{key}'.")
            continue
        if value is not None:
            error = spec.validate(value)
            if error:
                errors.append(error)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    changed: dict[str, dict[str, object]] = {}
    for key, value in payload.values.items():
        before = await service.get(key)
        if before == value:
            continue
        await service.set(key, value, updated_by=user_id)
        changed[key] = {"from": before, "to": value}

    if changed:
        await container.audit().record(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="platform_settings.changed",
            resource_type="platform_settings",
            detail=changed,
        )

    return ApiResponse(message="Platform settings saved.", data=await _response(service))
