# Notification models
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class SendEmailHeaders(BaseModel):
    tenant_id: str

    app_name: str

    app_url: str

    path: str

    idempotency_key: str | None = None
class EmailAttachment(BaseModel):
    filename: str
    content_type: str
    file_id: UUID


class SendEmailRequest(BaseModel):
    to: list[EmailStr]

    cc: list[EmailStr] = Field(default_factory=list)

    bcc: list[EmailStr] = Field(default_factory=list)

    subject: str

    html: str

    text: str | None = None

    attachments: list[EmailAttachment] = Field(
        default_factory=list,
    )


class SendTemplateEmailRequest(BaseModel):
    to: list[EmailStr]

    template: str

    variables: dict[str, object] = Field(
        default_factory=dict,
    )

    attachments: list[EmailAttachment] = Field(
        default_factory=list,
    )


class BulkEmailRequest(BaseModel):
    emails: list[SendEmailRequest]


class EmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    status: str

    created_at: datetime


class EmailStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    status: str

    provider: str

    sent_at: datetime | None = None

    delivered_at: datetime | None = None

    opened_at: datetime | None = None

    clicked_at: datetime | None = None
class SendEmailResponse(BaseModel):
    success: bool

    message: str