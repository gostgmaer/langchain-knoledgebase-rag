# Notification client
from __future__ import annotations

import httpx

from packages.config.notification import NotificationSettings

from .email import NotificationEmailSDK


class NotificationClient:
    """Notification SDK facade."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: NotificationSettings,
    ) -> None:

        self.email = NotificationEmailSDK(
            client=client,
            base_url=str(settings.base_url),
        )