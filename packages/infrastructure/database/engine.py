from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from packages.config.settings import Settings


def create_database_engine(
    settings: Settings,
) -> AsyncEngine:
    """
    Create the application's async SQLAlchemy engine.
    """

    url_str = str(settings.database.url)
    if url_str.startswith("postgresql://"):
        url_str = url_str.replace("postgresql://", "postgresql+asyncpg://", 1)

    return create_async_engine(
        url=url_str,
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
