# Notification exceptions
from __future__ import annotations

from packages.sdk.common.exceptions import SDKException


class NotificationSDKException(SDKException):
    """Notification SDK exception."""


class EmailNotFoundException(NotificationSDKException):
    """Email not found."""


class TemplateNotFoundException(NotificationSDKException):
    """Template not found."""


class EmailDeliveryException(NotificationSDKException):
    """Email delivery failed."""