# packages/api/security.py

from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

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


# Declared purely so Swagger UI shows an "Authorize" field for it,
# matching tenant_scheme above. The real validation/fail-open logic
# already runs in AuthenticationMiddleware (packages/api/middleware/
# authentication.py), which reads the raw header itself — this
# dependency doesn't duplicate that, it's just for OpenAPI discovery.
bearer_scheme = HTTPBearer(
    scheme_name="Authorization",
    description="Bearer access token issued by IAM. Optional — omit to use the default tenant/user identity.",
    auto_error=False,
)

async def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str | None:
    return credentials.credentials if credentials else None