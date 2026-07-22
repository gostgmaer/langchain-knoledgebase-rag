from __future__ import annotations

from typing import BinaryIO
from uuid import UUID

from packages.sdk.common.base_client import BaseClient

from ._headers import identity_headers
from .endpoints import UploadEndpoints
from .models import (
    CompleteMultipartRequest,
    MultipartPartsResponse,
    MultipartUpload,
    MultipartUploadRequest,
    PresignedUpload,
    PresignedUploadRequest,
    UploadedFile,
)


class UploadUploadsSDK(BaseClient):
    """Upload workflow SDK."""

    async def upload(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> UploadedFile:
        """
        Upload a file directly.

        `tenant_id` is required, not optional — the real Upload
        Service (INTEGRATION_GUIDE.md §4) does no authentication of
        its own and trusts `X-Tenant-Id` as a fact. Omitting it
        doesn't error, it silently stores the file under the
        service's own `DEFAULT_TENANT_ID` instead — every tenant's
        upload landing in the same bucket regardless of which one
        actually sent it. Making this required at the call site is
        the fix, not a docstring warning.

        The real Upload Service's multipart field is `files` (plural,
        even for a single file — confirmed live; `file` is rejected
        with "Unexpected field 'file'"), and its response `data` is
        always a list, even for one file. Takes the first (only) item.
        """

        response = await self._post(
            UploadEndpoints.UPLOAD,
            files={
                "files": (
                    filename,
                    file,
                    content_type,
                )
            },
            headers=identity_headers(tenant_id, user_id),
        )

        uploaded = self._unwrap(response)

        return UploadedFile.model_validate(uploaded[0])

    async def replace(
        self,
        file_id: str,
        file: BinaryIO,
        filename: str,
        content_type: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> UploadedFile:
        """
        Replace an existing file's binary content (`PUT /api/files/:id/replace`,
        INTEGRATION_GUIDE.md §7) — the old version is archived in
        `file.versions[]`. Field name is `file`, singular — the
        opposite of `upload()`'s `files`; confirmed in the guide's own
        troubleshooting section (§14), a real point of confusion
        between the two endpoints.
        """

        response = await self._put(
            UploadEndpoints.REPLACE.format(file_id=file_id),
            files={
                "file": (
                    filename,
                    file,
                    content_type,
                )
            },
            headers=identity_headers(tenant_id, user_id),
        )

        return UploadedFile.model_validate(self._unwrap(response)["file"])

    # ------------------------------------------------------------------
    # Presigned / multipart upload — CONFIRMED NOT PART OF THE REAL
    # SERVICE. `file-upload-service/docs/INTEGRATION_GUIDE.md` §7 lists
    # every endpoint the service actually has: upload, list, get,
    # download, rename, update, replace, delete, permanent-delete,
    # transactions, health — no presigned-URL or multipart/chunked
    # upload route exists anywhere in it. Calling any of the methods
    # below against the real service will just 404. Left in only in
    # case a future version of the service adds this; not a "maybe",
    # a documented "doesn't exist yet."
    # ------------------------------------------------------------------

    async def create_presigned_upload(
        self,
        request: PresignedUploadRequest,
    ) -> PresignedUpload:
        """Generate a presigned upload URL."""

        response = await self._post(
            UploadEndpoints.PRESIGNED_UPLOAD,
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return PresignedUpload.model_validate(
            self._unwrap(response),
        )

    async def confirm_presigned_upload(
        self,
        upload_id: UUID,
    ) -> UploadedFile:
        """Confirm a completed presigned upload."""

        response = await self._post(
            UploadEndpoints.PRESIGNED_CONFIRM.format(
                upload_id=upload_id,
            )
        )

        return UploadedFile.model_validate(
            self._unwrap(response),
        )

    async def initiate_multipart(
        self,
        request: MultipartUploadRequest,
    ) -> MultipartUpload:
        """Start multipart upload."""

        response = await self._post(
            UploadEndpoints.MULTIPART_INITIATE,
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return MultipartUpload.model_validate(
            self._unwrap(response),
        )

    async def get_upload_parts(
        self,
        upload_id: UUID,
        part_numbers: list[int],
    ) -> MultipartPartsResponse:
        """Request presigned URLs for multipart upload."""

        response = await self._post(
            UploadEndpoints.MULTIPART_PARTS.format(
                upload_id=upload_id,
            ),
            json={
                "parts": part_numbers,
            },
        )

        return MultipartPartsResponse.model_validate(
            self._unwrap(response),
        )

    async def complete_multipart(
        self,
        upload_id: UUID,
        request: CompleteMultipartRequest,
    ) -> UploadedFile:
        """Complete multipart upload."""

        response = await self._post(
            UploadEndpoints.MULTIPART_COMPLETE.format(
                upload_id=upload_id,
            ),
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return UploadedFile.model_validate(
            self._unwrap(response),
        )

    async def abort_multipart(
        self,
        upload_id: UUID,
    ) -> None:
        """Abort multipart upload."""

        await self._delete(
            UploadEndpoints.MULTIPART_ABORT.format(
                upload_id=upload_id,
            )
        )