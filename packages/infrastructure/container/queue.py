# Container queue setup
from __future__ import annotations

from dependency_injector import containers, providers


class QueueContainer(containers.DeclarativeContainer):
    """
    Producer-side handle to the arq Redis queue that packages/worker/
    consumes. `pool` starts as `None` and is only ever set by
    packages/api/lifespan.py, once a real connection to Redis succeeds
    — the same "never block startup, degrade instead of crash" idiom
    already used there for the Postgres checkpointer. Callers (see
    packages/api/routers/documents.py) must handle `pool` still being
    `None` if Redis was unreachable at startup.
    """

    pool = providers.Object(None)
