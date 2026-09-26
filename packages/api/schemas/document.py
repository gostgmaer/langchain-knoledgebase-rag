# Schema document
from __future__ import annotations

from datetime import datetime
from typing import Any
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


class ChunkingInfoSchema(BaseModel):
    """How a document was split, recorded at ingestion (Document.metadata_["chunking"])."""

    requested: str | None = None
    """What the uploader asked for: auto | recursive | markdown | semantic."""
    strategy: str | None = None
    """What actually ran. Differs from `requested` when it was "auto"."""
    splitter: str | None = None
    """The splitter class that produced the chunks."""
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunk_count: int | None = None
    total_tokens: int | None = None


class DocumentResponseSchema(BaseModel):
    """A single document's metadata (not its chunk content — see GET /documents/{id}/chunks)."""

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

    chunk_count: int = 0
    """Primary chunks stored for this document (counted from the database)."""
    representation_count: int = 0
    """Extra retrieval representations (document summary, graph) - not chunks of the text."""
    chunking: ChunkingInfoSchema | None = None
    """None for documents ingested before chunking was recorded."""
    document_metadata: dict[str, Any] = {}
    """Everything else stored on the document row (upload metadata, chunking record...)."""

    # Provenance / processing record. None = not recorded (ingested before these existed).
    content_hash: str | None = None
    uploaded_by: UUID | None = None
    source_type: str | None = None
    processing_version: str | None = None
    parser_name: str | None = None
    chunking_version: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    processing_stage: str | None = None
    error_reason: str | None = None
    processed_at: datetime | None = None
    embedding_is_stale: bool | None = None
    """True when embedded by an older pipeline than the running one; None when never recorded."""


class DocumentChunkResponseSchema(BaseModel):
    """One stored chunk with everything the database keeps about it."""

    id: UUID
    chunk_index: int
    """0.. for the document's text chunks; negative for summary/graph representations."""
    kind: str
    """"chunk", or the representation type ("summary", "graph"...)."""
    page_number: int | None
    section: str | None
    content: str
    token_count: int
    character_count: int
    start_offset: int | None
    end_offset: int | None
    metadata: dict[str, Any]
    """The chunk's full metadata: source, page, headings, chunking strategy, ingested_at..."""

    # Provenance columns. None = not recorded (chunk stored before these existed).
    content_hash: str | None = None
    chunking_strategy: str | None = None
    chunking_version: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    pipeline_version: str | None = None
    indexed_at: datetime | None = None


class DocumentChunkListResponseSchema(BaseModel):
    """A page of one document's chunks."""

    document_id: UUID
    total: int
    limit: int
    offset: int
    chunking: ChunkingInfoSchema | None
    chunks: list[DocumentChunkResponseSchema]


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
    """Set by the router, not read from the DB row directly — True for the
    one entry whose superseded_at is still null."""


class DocumentVersionListResponseSchema(BaseModel):
    """A document's full version history, oldest first."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    root_document_id: UUID
    versions: list[DocumentVersionResponseSchema]
