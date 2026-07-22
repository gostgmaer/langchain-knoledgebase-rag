from __future__ import annotations

from packages.sdk.common.base_client import BaseClient

from .endpoints import UploadEndpoints
from .models import (
    BulkDeleteRequest,
    BulkMetadataRequest,
    BulkOperationResponse,
    SignedUrl,
    SignedUrlRequest,
)


class UploadBulkSDK(BaseClient):
    """
    Bulk upload operations — CONFIRMED NOT PART OF THE REAL SERVICE.
    `file-upload-service/docs/INTEGRATION_GUIDE.md` §7's full endpoint
    list has no `/api/files/bulk/*` routes at all (single-file
    operations only: rename, update, replace, delete each take one
    `:id`). Calling any method here against the real service will
    404. Kept only in case a future version adds this.
    """

    async def delete(
        self,
        request: BulkDeleteRequest,
    ) -> BulkOperationResponse:
        """Soft delete multiple files."""

        response = await self._post(
            UploadEndpoints.BULK_DELETE,
            json=request.model_dump(),
        )

        return BulkOperationResponse.model_validate(
            self._unwrap(response),
        )

    async def permanent_delete(
        self,
        request: BulkDeleteRequest,
    ) -> BulkOperationResponse:
        """Permanently delete multiple files."""

        response = await self._post(
            UploadEndpoints.BULK_PERMANENT_DELETE,
            json=request.model_dump(),
        )

        return BulkOperationResponse.model_validate(
            self._unwrap(response),
        )

    async def update_metadata(
        self,
        request: BulkMetadataRequest,
    ) -> BulkOperationResponse:
        """Update metadata for multiple files."""

        response = await self._patch(
            UploadEndpoints.BULK_METADATA,
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return BulkOperationResponse.model_validate(
            self._unwrap(response),
        )

    async def create_signed_urls(
        self,
        request: SignedUrlRequest,
    ) -> list[SignedUrl]:
        """Generate signed download URLs."""

        response = await self._post(
            UploadEndpoints.BULK_SIGNED_URLS,
            json=request.model_dump(),
        )

        return [
            SignedUrl.model_validate(item)
            for item in self._unwrap(response)
        ]