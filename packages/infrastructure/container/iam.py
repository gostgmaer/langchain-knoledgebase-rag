# Container IAM setup
from __future__ import annotations

from dependency_injector import containers, providers

from packages.auth.service import AuthService
from packages.config.loader import settings as app_settings
from packages.infrastructure.http.client import create_http_client
from packages.sdk.iam.client import IAMClient


class IAMContainer(
    containers.DeclarativeContainer,
):
    """
    Wires the IAM SDK client and the AuthService that resolves the
    current user from a bearer token (fails open — see
    packages/auth/service.py).
    """

    database = providers.DependenciesContainer()

    http_client = providers.Singleton(
        create_http_client,
    )

    client = providers.Singleton(
        IAMClient,
        client=http_client,
        settings=app_settings.iam,
    )

    auth_service = providers.Singleton(
        AuthService,
        client=client,
        # Lets AuthService resolve this app's own API keys (docs/BUGS.md item 33) without going
        # through the request-scoped session machinery — a short-lived session opened and closed
        # entirely within AuthService, since the auth middleware runs before any route-level
        # dependency establishes one.
        api_key_session_factory=database.session_factory,
    )
