# Schema upload job
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadJobResponseSchema(BaseModel):
    """Real pipeline progress for one document upload."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    file_name: str
    status: str
    document_id: UUID | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
