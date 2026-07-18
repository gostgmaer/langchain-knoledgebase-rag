from __future__ import annotations

from dependency_injector import containers, providers

from packages.config import get_settings
from packages.infrastructure.database.engine import create_database_engine
from packages.infrastructure.database.session import (
    create_session,
    create_session_factory,
)
from packages.infrastructure.http.client import create_http_client
from packages.logging import get_logger
from packages.infrastructure.redis.client import (
    create_redis_client,
)
from packages.sdk.iam import IAMClient


class ApplicationContainer(containers.DeclarativeContainer):
    """Application dependency container."""

    wiring_config = containers.WiringConfiguration()

    # Configuration
    settings = providers.Singleton(get_settings)

    # Logger
    logger = providers.Singleton(
        get_logger,
        name="easydev-ai",
    )

    # Database
    database_engine = providers.Singleton(
        create_database_engine,
        settings=settings.provided.database,
    )

    session_factory = providers.Singleton(
        create_session_factory,
        engine=database_engine,
    )

    db_session = providers.Factory(
        create_session,
        session_factory=session_factory,
    )
    # Redis
    redis = providers.Singleton(
        create_redis_client,
        settings=settings.provided.redis,
    )
    # Http
    http_client = providers.Singleton(
        create_http_client,
    )
    # iam
    iam_client = providers.Singleton(
        IAMClient,
        client=http_client,
        settings=settings.provided.iam,
    )
