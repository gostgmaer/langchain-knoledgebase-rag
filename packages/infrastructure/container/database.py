# Container database
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.infrastructure.database.engine import DatabaseEngine
from packages.infrastructure.database.session import SessionManager
from packages.infrastructure.database.transaction import UnitOfWork

from .settings import SettingsContainer


class DatabaseContainer(
    containers.DeclarativeContainer,
):

    settings = providers.DependenciesContainer()
    engine = providers.Singleton(
        DatabaseEngine,
        settings.config,
    )

    session = providers.Singleton(
        SessionManager,
        engine=engine,
    )

    uow = providers.Factory(
        UnitOfWork,
        session_factory=session.provided.session,
    )