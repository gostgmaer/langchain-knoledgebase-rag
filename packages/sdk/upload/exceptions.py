# Upload exceptions
from __future__ import annotations

from packages.sdk.common.exceptions import SDKException


class UploadSDKException(SDKException):
    """Base upload SDK exception."""


class FileNotFoundException(UploadSDKException):
    """File not found."""


class UploadNotFoundException(UploadSDKException):
    """Upload session not found."""


class MultipartUploadException(UploadSDKException):
    """Multipart upload failed."""


class InvalidFileException(UploadSDKException):
    """Invalid file."""


class FileTooLargeException(UploadSDKException):
    """File exceeds maximum size."""