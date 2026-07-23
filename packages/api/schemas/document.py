# Schema document
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentUploadResponseSchema(BaseModel):
    """
    Acknowledgement that an upload was accepted for background
    ingestion. Indexing (load/clean/split/embed/store) runs off the
    request path — this response confirms the file was received and
    queued, not that indexing has finished. The real outcome
    (created, skipped as an unchanged re-upload, or failed) is only
    known once the background task completes.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    status: str
    document_name: str
    file_id: str
    """The Upload Service's own file ID — a Mongo ObjectId string, not a UUID."""
    upload_job_id: UUID
    """Poll GET /api/v1/upload-jobs/{id} for real pipeline progress."""


class DocumentResponseSchema(BaseModel):
    """A single document's metadata (not its chunk content — see docs/ARCHITECTURE_TUTORIAL.md §5.2)."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    knowledge_base_id: UUID
    title: str
    description: str | None
    file_id: str
    file_name: str
    mime_type: str
    extension: str
    size_bytes: int
    status: str
    is_current: bool
    created_at: datetime
    updated_at: datetime


class DocumentListResponseSchema(BaseModel):
    """A page of a tenant's documents, most recent first."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    documents: list[DocumentResponseSchema]


class DocumentVersionResponseSchema(BaseModel):
    """One entry in a document's version lineage."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    document_id: UUID
    version_number: int
    superseded_at: datetime | None
    is_current: bool = False
    """Set by the router, not read from the DB row directly — True for the one entry whose superseded_at is still null."""


class DocumentVersionListResponseSchema(BaseModel):
    """A document's full version history, oldest first."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    root_document_id: UUID
    versions: list[DocumentVersionResponseSchema]
