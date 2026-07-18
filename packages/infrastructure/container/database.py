from dependency_injector import providers,containers

from packages.infrastructure.database.engine import create_database_engine
from packages.infrastructure.database.session import create_session_factory
from packages.infrastructure.database.transaction import UnitOfWork


class DatabaseContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()

    engine = providers.Singleton(
        create_database_engine,
        settings=settings.config,
    )

    session = providers.Singleton(
        create_session_factory,
        engine=engine,
    )

    uow = providers.Factory(
        UnitOfWork,
        session_factory=session.provided.session,
    )