# Notification endpoints
from __future__ import annotations


class NotificationEndpoints:
    """Notification Service endpoints."""

    HEALTH = "/health"

    SEND_EMAIL = "/v1/email/send"

    SEND_TEMPLATE = "/api/emails/template"

    SEND_BULK = "/api/emails/bulk"

    EMAIL_STATUS = "/api/emails/{email_id}"