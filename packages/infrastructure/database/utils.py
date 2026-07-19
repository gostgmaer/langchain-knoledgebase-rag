from __future__ import annotations


def to_sync_database_url(url: str) -> str:
    """
    Convert any PostgreSQL URL to psycopg for Alembic.

    Supported:
        postgresql://
        postgresql+asyncpg://
        postgresql+psycopg://
    """

    if url.startswith("postgresql+psycopg://"):
        return url

    if url.startswith("postgresql+asyncpg://"):
        return url.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg://",
            1,
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return url