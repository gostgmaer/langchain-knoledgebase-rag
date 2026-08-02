from __future__ import annotations

from sqlalchemy import engine_from_config, pool

from alembic import context
from packages.config.settings import Settings

# Import every ORM model
from packages.domain import models  # noqa: F401
from packages.infrastructure.database.base import Base
from packages.infrastructure.database.utils import to_sync_database_url

target_metadata = Base.metadata


def _configure_url() -> None:
    """
    Sets alembic's `sqlalchemy.url` from this app's real
    `DatabaseSettings`. Deliberately a function, not module-level code
    — `alembic.context.config` only exists once alembic's own CLI has
    bootstrapped a real `EnvironmentContext` (`alembic upgrade`,
    `alembic revision`, etc. via `alembic/env.py`); touching it at
    import time made this module raise `AttributeError: module
    'alembic.context' has no attribute 'config'` for anything that
    just imports it directly (a plain import sweep, an IDE indexer) —
    a real, previously-tracked-but-unfixed failure, not a behavior
    change for actual migration runs, which already only ever import
    this module from inside `alembic/env.py`.
    """

    settings = Settings()

    context.config.set_main_option(
        "sqlalchemy.url",
        to_sync_database_url(str(settings.database.url)),
    )


def run_migrations_offline() -> None:
    _configure_url()

    context.configure(
        url=context.config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _configure_url()

    connectable = engine_from_config(
        context.config.get_section(context.config.config_ini_section),
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