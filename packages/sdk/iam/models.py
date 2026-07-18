from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Permission(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str


class Role(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str

    permissions: list[Permission] = []


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID

    email: str

    first_name: str
    last_name: str

    is_active: bool
    is_verified: bool

    created_at: datetime
    updated_at: datetime


class Tenant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    name: str
    slug: str

    is_active: bool


class CurrentUser(User):
    roles: list[Role] = []
    permissions: list[Permission] = []


class ServiceToken(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str

    token_type: str

    expires_in: int


class IntrospectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active: bool

    session_id: UUID

    user_id: UUID

    tenant_id: UUID

    roles: list[Role]

    permissions: list[Permission]