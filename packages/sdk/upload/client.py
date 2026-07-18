from __future__ import annotations

import httpx

from packages.config.upload import UploadSettings

from .bulk import UploadBulkSDK
from .files import UploadFilesSDK
from .uploads import UploadUploadsSDK


class UploadClient:
    """Upload Service SDK."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: UploadSettings,
    ) -> None:

        self.files = UploadFilesSDK(
            client=client,
            base_url=str(settings.base_url),
        )

        self.uploads = UploadUploadsSDK(
            client=client,
            base_url=str(settings.base_url),
        )

        self.bulk = UploadBulkSDK(
            client=client,
            base_url=str(settings.base_url),
        )