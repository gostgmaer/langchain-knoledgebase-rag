# Schema user
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponseSchema(BaseModel):
    """A user's real name/email, resolved from IAM — this app only ever stores a user_id."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    is_active: bool


class UserListResponseSchema(BaseModel):
    """Every real member of a tenant, resolved from IAM (docs/BUGS.md item 32)."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    users: list[UserResponseSchema]
