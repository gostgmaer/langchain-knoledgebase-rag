# Schema tenant
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantResponseSchema(BaseModel):
    """
    A tenant's real name/slug, resolved from IAM (the system of record for
    organizations — this app only ever stores a `tenant_id`, never a name).
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    slug: str
    is_active: bool
