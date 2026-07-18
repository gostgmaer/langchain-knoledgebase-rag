from __future__ import annotations

from uuid import UUID

from packages.sdk.common.base_client import BaseClient

from .endpoints import UploadEndpoints
from .models import (
    FileListResponse,
    FileTransaction,
    RenameFileRequest,
    UpdateMetadataRequest,
    UploadedFile,
)


class UploadFilesSDK(BaseClient):

    async def health(self) -> bool:
        await self._get(
            UploadEndpoints.HEALTH,
        )
        return True

    async def list_files(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ) -> FileListResponse:

        response = await self._get(
            UploadEndpoints.FILES,
            params={
                "page": page,
                "limit": limit,
                "search": search,
            },
        )

        return FileListResponse.model_validate(
            response.json(),
        )

    async def get_file(
        self,
        file_id: UUID,
    ) -> UploadedFile:

        response = await self._get(
            UploadEndpoints.FILE.format(
                file_id=file_id,
            )
        )

        return UploadedFile.model_validate(
            response.json(),
        )

    async def download(
        self,
        file_id: UUID,
    ) -> bytes:

        response = await self._get(
            UploadEndpoints.DOWNLOAD.format(
                file_id=file_id,
            )
        )

        return response.content

    async def update_metadata(
        self,
        file_id: UUID,
        request: UpdateMetadataRequest,
    ) -> UploadedFile:

        response = await self._patch(
            UploadEndpoints.UPDATE_METADATA.format(
                file_id=file_id,
            ),
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return UploadedFile.model_validate(
            response.json(),
        )

    async def rename(
        self,
        file_id: UUID,
        filename: str,
    ) -> UploadedFile:

        response = await self._patch(
            UploadEndpoints.RENAME.format(
                file_id=file_id,
            ),
            json=RenameFileRequest(
                filename=filename,
            ).model_dump(),
        )

        return UploadedFile.model_validate(
            response.json(),
        )

    async def delete(
        self,
        file_id: UUID,
    ) -> None:

        await self._delete(
            UploadEndpoints.DELETE.format(
                file_id=file_id,
            )
        )

    async def permanent_delete(
        self,
        file_id: UUID,
    ) -> None:

        await self._delete(
            UploadEndpoints.PERMANENT_DELETE.format(
                file_id=file_id,
            )
        )

    async def get_transactions(
        self,
        file_id: UUID,
    ) -> list[FileTransaction]:

        response = await self._get(
            UploadEndpoints.TRANSACTIONS.format(
                file_id=file_id,
            )
        )

        return [
            FileTransaction.model_validate(item)
            for item in response.json()
        ]