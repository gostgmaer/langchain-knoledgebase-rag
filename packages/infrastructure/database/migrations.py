from __future__ import annotations

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from packages.config.settings import Settings
from packages.infrastructure.database.base import Base
from packages.infrastructure.database.utils import to_sync_database_url

# Import every ORM model
from packages.domain import models  # noqa: F401

settings = Settings()

config = context.config

config.set_main_option(
    "sqlalchemy.url",
    to_sync_database_url(str(settings.database.url)),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()