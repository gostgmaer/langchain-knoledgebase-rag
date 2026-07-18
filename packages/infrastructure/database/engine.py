from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from packages.config import get_settings


def create_database_engine() -> AsyncEngine:
    """Create the application's async SQLAlchemy engine."""

    settings = get_settings()

    return create_async_engine(
        url=str(settings.database.url),
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )