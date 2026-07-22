# Schema document
from __future__ import annotations

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
