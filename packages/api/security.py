# packages/api/security.py

from fastapi import Depends
from fastapi.security import APIKeyHeader

from packages.api.middleware.tenant import DEFAULT_TENANT_ID

tenant_scheme = APIKeyHeader(
    name="X-Tenant-Id",
    scheme_name="Tenant",
    description="Tenant Identifier",
    auto_error=False,
)

async def get_tenant_id(
    tenant_id: str | None = Depends(tenant_scheme),
) -> str:
    return tenant_id or DEFAULT_TENANT_ID