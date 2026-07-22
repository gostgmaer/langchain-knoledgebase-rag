# Container Upload Service setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.config.loader import settings as app_settings
from packages.infrastructure.http.client import create_http_client
from packages.sdk.upload.client import UploadClient


class UploadContainer(
    containers.DeclarativeContainer,
):
    """
    Wires the Upload Service SDK client — a separate, external file
    storage microservice (presigned/multipart S3-style uploads), kept
    deliberately outside this app so document bytes don't pile up on
    this app's own local disk (see packages/api/routers/documents.py).
    """

    http_client = providers.Singleton(
        create_http_client,
    )

    client = providers.Singleton(
        UploadClient,
        client=http_client,
        settings=app_settings.upload_service,
    )
