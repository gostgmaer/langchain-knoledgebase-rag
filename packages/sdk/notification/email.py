from __future__ import annotations

from uuid import UUID

from packages.sdk.common.base_client import BaseClient

from .endpoints import NotificationEndpoints
from .models import (
    BulkEmailRequest,
    EmailResponse,
    EmailStatus,
    SendEmailHeaders,
    SendEmailRequest,
    SendEmailResponse,
    SendTemplateEmailRequest,
)


class NotificationEmailSDK(BaseClient):
    """Email operations for Notification Service."""

    async def health(self) -> bool:
        """Check notification service health."""

        await self._get(
            NotificationEndpoints.HEALTH,
        )

        return True

    async def send(
        self,
        request: SendEmailRequest,
        headers: SendEmailHeaders,
    ) -> SendEmailResponse:

        response = await self._post(
            NotificationEndpoints.SEND_EMAIL,
            json=request.model_dump(),
            headers={
                "x-tenant-id": headers.tenant_id,
                "x-app-name": headers.app_name,
                "x-app-url": headers.app_url,
                "x-path": headers.path,
                **(
                    {"x-idempotency-key": headers.idempotency_key}
                    if headers.idempotency_key
                    else {}
                ),
            },
        )

        return SendEmailResponse.model_validate(
            response.json()
        )

    async def send_template(
        self,
        request: SendTemplateEmailRequest,
    ) -> EmailResponse:
        """Send an email using a stored template."""

        response = await self._post(
            NotificationEndpoints.SEND_TEMPLATE,
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return EmailResponse.model_validate(
            response.json(),
        )

    async def send_bulk(
        self,
        request: BulkEmailRequest,
    ) -> list[EmailResponse]:
        """Send multiple emails."""

        response = await self._post(
            NotificationEndpoints.SEND_BULK,
            json=request.model_dump(
                exclude_none=True,
            ),
        )

        return [
            EmailResponse.model_validate(item)
            for item in response.json()
        ]

    async def get_status(
        self,
        email_id: UUID,
    ) -> EmailStatus:
        """Get email delivery status."""

        response = await self._get(
            NotificationEndpoints.EMAIL_STATUS.format(
                email_id=email_id,
            )
        )

        return EmailStatus.model_validate(
            response.json(),
        )