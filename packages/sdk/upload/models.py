from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl


# ============================================================
# Base Models
# ============================================================


class FileMetadata(BaseModel):
    """Nested `metadata` object the real Upload Service returns on every file."""

    model_config = ConfigDict(populate_by_name=True)

    description: str = ""

    tags: list[str] = Field(default_factory=list)

    custom: dict[str, str] = Field(default_factory=dict)

    title: str = ""

    alt_text: str = Field(default="", alias="altText")

    author: str = ""

    source: str = ""

    language: str = ""

    is_public: bool = Field(default=False, alias="isPublic")

    linked_to: dict[str, str] = Field(default_factory=dict, alias="linkedTo")


class UploadedFile(BaseModel):
    """
    Uploaded file metadata, matching the real Upload Service's actual
    response shape (confirmed live against https://fms.easydev.in —
    Mongo-backed, camelCase fields, no relation to the originally
    assumed S3-style bucket/object_key/UUID shape this SDK was first
    written against). `id` is a Mongo ObjectId string, not a UUID.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str

    tenant_id: str = Field(alias="tenantId")

    original_name: str = Field(alias="originalName")

    storage_key: str = Field(alias="storageKey")

    size: int

    mime_type: str = Field(alias="mimeType")

    extension: str

    uploader: str = "anonymous"

    category: str = ""

    status: str

    scan_status: str = Field(default="", alias="scanStatus")

    # The real service isn't consistent about this field's name across
    # endpoints — confirmed live: `url` on upload/get-by-id responses,
    # `publicUrl` on list responses; INTEGRATION_GUIDE.md's own File
    # Object Shape example uses `publicUrl` too. Accept either.
    url: str | None = Field(default=None, validation_alias=AliasChoices("url", "publicUrl"))

    metadata: FileMetadata = Field(default_factory=FileMetadata)

    versions: list[dict] = Field(default_factory=list)

    created_at: datetime = Field(alias="createdAt")

    updated_at: datetime = Field(alias="updatedAt")


# ============================================================
# List
# ============================================================


class Pagination(BaseModel):
    page: int

    limit: int

    total: int

    pages: int


class FileListResponse(BaseModel):
    files: list[UploadedFile]

    pagination: Pagination


# ============================================================
# Metadata
# ============================================================


class MetadataUpdate(BaseModel):
    """
    The nested `metadata` object inside `PATCH /api/files/:id`'s body
    (INTEGRATION_GUIDE.md §7) — a *partial* update, so every field is
    optional and only ones actually set get sent (`exclude_none=True`
    at the call site), rather than overwriting the rest with defaults.
    """

    description: str | None = None

    title: str | None = None

    alt_text: str | None = Field(default=None, alias="altText")

    author: str | None = None

    source: str | None = None

    language: str | None = None

    expires_at: datetime | None = Field(default=None, alias="expiresAt")

    is_public: bool | None = Field(default=None, alias="isPublic")

    tags: list[str] | None = None

    custom: dict[str, str] | None = None

    linked_to: dict[str, str] | None = Field(default=None, alias="linkedTo")

    model_config = ConfigDict(populate_by_name=True)


class UpdateMetadataRequest(BaseModel):
    """
    `PATCH /api/files/:id`'s real body shape — `originalName`/
    `category` are top-level, everything else nests under `metadata`.
    Previously modeled as a flat `{metadata: {...}, tags: [...]}`,
    which doesn't match the real service at all.
    """

    original_name: str | None = Field(default=None, alias="originalName")

    category: str | None = None

    metadata: MetadataUpdate | None = None

    model_config = ConfigDict(populate_by_name=True)


class RenameFileRequest(BaseModel):
    """`PATCH /api/files/:id/rename`'s body is `{"name": "..."}`, not `{"filename": "..."}`."""

    name: str


# ============================================================
# Upload
#
# Everything below this point (presigned upload, multipart upload,
# bulk operations) has NO corresponding endpoint anywhere in the real
# Upload Service's own INTEGRATION_GUIDE.md — its full, explicit §7
# endpoint list is: upload, list, get, download, rename, update,
# replace, delete, permanent-delete, transactions, health. No
# presigned/multipart/bulk routes exist. These models and the SDK
# methods that use them are speculative, calling them will 404
# against the real service, and they're kept only in case a future
# version of the service adds this — not because they currently work.
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
    """Matches INTEGRATION_GUIDE.md §5's Transaction Object Shape exactly."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")

    tenant_id: str = Field(alias="tenantId")

    file_id: str = Field(alias="fileId")

    operation: str

    status: str

    performed_by: str = Field(alias="performedBy")

    request_id: str = Field(alias="requestId")

    payload: dict = Field(default_factory=dict)

    provider_response: dict = Field(default_factory=dict, alias="providerResponse")

    created_at: datetime = Field(alias="createdAt")

    updated_at: datetime = Field(alias="updatedAt")