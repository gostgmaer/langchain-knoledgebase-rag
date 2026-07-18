from __future__ import annotations

from typing import BinaryIO
from uuid import UUID

from packages.sdk.common.base_client import BaseClient

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
    ) -> UploadedFile:
        """Upload a file directly."""

        response = await self._post(
            UploadEndpoints.UPLOAD,
            files={
                "file": (
                    filename,
                    file,
                    content_type,
                )
            },
        )

        return UploadedFile.model_validate(
            response.json(),
        )

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
            response.json(),
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
            response.json(),
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
            response.json(),
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
            response.json(),
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
            response.json(),
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