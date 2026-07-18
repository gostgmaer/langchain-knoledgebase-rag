from __future__ import annotations


class UploadEndpoints:
    """Upload Service API endpoints."""

    # ============================================================
    # Health
    # ============================================================

    ROOT = "/"

    HEALTH = "/health"

    HEALTH_LIVE = "/health/live"

    HEALTH_READY = "/health/ready"

    METRICS = "/metrics"

    # ============================================================
    # File Management
    # ============================================================

    FILES = "/api/files"

    FILE = "/api/files/{file_id}"

    DOWNLOAD = "/api/files/{file_id}/download"

    UPDATE_METADATA = "/api/files/{file_id}"

    RENAME = "/api/files/{file_id}/rename"

    REPLACE = "/api/files/{file_id}/replace"

    DELETE = "/api/files/{file_id}"

    PERMANENT_DELETE = "/api/files/{file_id}/permanent"

    TRANSACTIONS = "/api/files/{file_id}/transactions"

    # ============================================================
    # Upload
    # ============================================================

    UPLOAD = "/api/files/upload"

    PRESIGNED_UPLOAD = "/api/files/upload/presign"

    PRESIGNED_CONFIRM = "/api/files/upload/presign/{upload_id}/confirm"

    # ============================================================
    # Multipart Upload
    # ============================================================

    MULTIPART_INITIATE = "/api/files/upload/multipart/initiate"

    MULTIPART_PARTS = "/api/files/upload/multipart/{upload_id}/parts"

    MULTIPART_COMPLETE = "/api/files/upload/multipart/{upload_id}/complete"

    MULTIPART_ABORT = "/api/files/upload/multipart/{upload_id}/abort"

    # ============================================================
    # Bulk
    # ============================================================

    BULK_DELETE = "/api/files/bulk/delete"

    BULK_PERMANENT_DELETE = "/api/files/bulk/permanent-delete"

    BULK_METADATA = "/api/files/bulk/metadata"

    BULK_SIGNED_URLS = "/api/files/bulk/signed-urls"