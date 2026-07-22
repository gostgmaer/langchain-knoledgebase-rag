from __future__ import annotations

from packages.sdk.common.base_client import BaseClient

from ._headers import identity_headers
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
        tenant_id: str,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ) -> FileListResponse:
        """
        The real service's Joi schema rejects `search` outright if
        it's present but empty ("search is not allowed to be empty")
        — confirmed live. `search=None` must be omitted from the query
        string entirely, not sent as an empty string.
        """

        params: dict[str, str | int] = {"page": page, "limit": limit}

        if search:
            params["search"] = search

        response = await self._get(
            UploadEndpoints.FILES,
            params=params,
            headers=identity_headers(tenant_id),
        )

        return FileListResponse.model_validate(
            self._unwrap(response),
        )

    async def get_file(
        self,
        file_id: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> UploadedFile:
        """
        `GET /api/files/:id` — INTEGRATION_GUIDE.md §7 documents
        `X-User-Id` as optional here, but the real service 404s
        ("File not found") without it even for a file that genuinely
        exists and belongs to the given tenant; confirmed live by
        comparing the same request with and without it. Pass it
        whenever it's available, not just when the guide says it's
        required.
        """

        response = await self._get(
            UploadEndpoints.FILE.format(
                file_id=file_id,
            ),
            headers=identity_headers(tenant_id, user_id),
        )

        return UploadedFile.model_validate(
            self._unwrap(response),
        )

    async def download(
        self,
        file_id: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> bytes:

        response = await self._get(
            UploadEndpoints.DOWNLOAD.format(
                file_id=file_id,
            ),
            headers=identity_headers(tenant_id, user_id),
        )

        return response.content

    async def update_metadata(
        self,
        file_id: str,
        request: UpdateMetadataRequest,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> UploadedFile:
        """
        `PATCH /api/files/:id` — response is `{file: {...}, requestId}`
        (INTEGRATION_GUIDE.md §7), not the bare File Object directly,
        so `data["file"]` is pulled out, not `data` itself.
        """

        response = await self._patch(
            UploadEndpoints.UPDATE_METADATA.format(
                file_id=file_id,
            ),
            json=request.model_dump(
                exclude_none=True,
                by_alias=True,
            ),
            headers=identity_headers(tenant_id, user_id),
        )

        return UploadedFile.model_validate(
            self._unwrap(response)["file"],
        )

    async def rename(
        self,
        file_id: str,
        name: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> UploadedFile:
        """
        `PATCH /api/files/:id/rename` — body is `{"name": "..."}`, and
        the response is `{file: {...}, requestId}` (INTEGRATION_GUIDE.md
        §7), same nested shape as `update_metadata` above.
        """

        response = await self._patch(
            UploadEndpoints.RENAME.format(
                file_id=file_id,
            ),
            json=RenameFileRequest(
                name=name,
            ).model_dump(),
            headers=identity_headers(tenant_id, user_id),
        )

        return UploadedFile.model_validate(
            self._unwrap(response)["file"],
        )

    async def delete(
        self,
        file_id: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> None:

        await self._delete(
            UploadEndpoints.DELETE.format(
                file_id=file_id,
            ),
            headers=identity_headers(tenant_id, user_id),
        )

    async def permanent_delete(
        self,
        file_id: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> None:

        await self._delete(
            UploadEndpoints.PERMANENT_DELETE.format(
                file_id=file_id,
            ),
            headers=identity_headers(tenant_id, user_id),
        )

    async def get_transactions(
        self,
        file_id: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
    ) -> list[FileTransaction]:
        """
        `GET /api/files/:id/transactions` — INTEGRATION_GUIDE.md §7
        lists only `X-Tenant-Id` as a header for this route, but the
        real service rejected it live with `401 — "Admin
        authentication required"` even with a valid tenant/user pair
        that worked for every other endpoint. This route needs
        whatever admin/gateway-signature auth scheme protects the
        service's root `/` route (also undocumented in the guide) —
        not yet wired into this SDK since `UploadServiceSettings`
        (`packages/config/upload_service.py`) has no field for it and
        nothing in this app currently calls this method.
        """

        response = await self._get(
            UploadEndpoints.TRANSACTIONS.format(
                file_id=file_id,
            ),
            headers=identity_headers(tenant_id, user_id),
        )

        return [
            FileTransaction.model_validate(item)
            for item in self._unwrap(response)
        ]
