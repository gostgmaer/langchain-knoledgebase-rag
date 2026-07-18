# packages/api/security.py

from fastapi import Depends
from fastapi.security import APIKeyHeader

tenant_scheme = APIKeyHeader(
    name="X-Tenant-Id",
    scheme_name="Tenant",
    description="Tenant Identifier",
    auto_error=True,
)

async def get_tenant_id(
    tenant_id: str = Depends(tenant_scheme),
) -> str:
    return tenant_id