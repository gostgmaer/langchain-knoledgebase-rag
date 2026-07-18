from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# ============================================================
# Base Models
# ============================================================


class UploadedFile(BaseModel):
    """Uploaded file metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    tenant_id: UUID

    filename: str

    original_filename: str

    content_type: str

    extension: str

    size: int

    checksum: str | None = None

    storage_provider: str

    bucket: str

    object_key: str

    version: int

    metadata: dict[str, str] = Field(default_factory=dict)

    tags: list[str] = Field(default_factory=list)

    is_deleted: bool

    created_at: datetime

    updated_at: datetime


# ============================================================
# List
# ============================================================


class Pagination(BaseModel):
    page: int

    limit: int

    total: int

    pages: int


class FileListResponse(BaseModel):
    items: list[UploadedFile]

    pagination: Pagination


# ============================================================
# Metadata
# ============================================================


class UpdateMetadataRequest(BaseModel):
    metadata: dict[str, str] = Field(default_factory=dict)

    tags: list[str] = Field(default_factory=list)


class RenameFileRequest(BaseModel):
    filename: str


# ============================================================
# Upload
# ============================================================


class PresignedUploadRequest(BaseModel):
    filename: str

    content_type: str

    size: int

    metadata: dict[str, str] = Field(default_factory=dict)


class PresignedUpload(BaseModel):
    upload_id: UUID

    file_id: UUID

    upload_url: HttpUrl

    expires_in: int


# ============================================================
# Multipart Upload
# ============================================================


class MultipartUploadRequest(BaseModel):
    filename: str

    content_type: str

    size: int


class MultipartUpload(BaseModel):
    upload_id: UUID

    file_id: UUID


class MultipartPart(BaseModel):
    part_number: int

    upload_url: HttpUrl


class MultipartPartsResponse(BaseModel):
    upload_id: UUID

    parts: list[MultipartPart]


class CompletedPart(BaseModel):
    part_number: int

    etag: str


class CompleteMultipartRequest(BaseModel):
    parts: list[CompletedPart]


# ============================================================
# Bulk
# ============================================================


class BulkDeleteRequest(BaseModel):
    file_ids: list[UUID]


class BulkMetadataItem(BaseModel):
    file_id: UUID

    metadata: dict[str, str] = Field(default_factory=dict)

    tags: list[str] = Field(default_factory=list)


class BulkMetadataRequest(BaseModel):
    files: list[BulkMetadataItem]


class BulkOperationResponse(BaseModel):
    success: int

    failed: int

    message: str


# ============================================================
# Signed URLs
# ============================================================


class SignedUrl(BaseModel):
    file_id: UUID

    url: HttpUrl

    expires_in: int


class SignedUrlRequest(BaseModel):
    file_ids: list[UUID]


class SignedUrlResponse(BaseModel):
    urls: list[SignedUrl]


# ============================================================
# Transactions / Audit
# ============================================================


class FileTransaction(BaseModel):
    id: UUID

    action: str

    user_id: UUID

    created_at: datetime

    details: dict[str, str] = Field(default_factory=dict)