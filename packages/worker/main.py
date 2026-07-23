from __future__ import annotations

from typing import Any

from arq import cron, run_worker
from arq.connections import RedisSettings as ArqRedisSettings

from packages.config.loader import settings
from packages.infrastructure.container import ApplicationContainer
from packages.shared.logging import configure_logger, get_logger
from packages.worker.jobs import cleanup_orphaned_scratch_files, ingest_document_job

logger = get_logger(__name__)


async def _on_startup(ctx: dict[str, Any]) -> None:
    # One long-lived container per worker process, mirroring how
    # packages/api/lifespan.py builds exactly one for the API process.
    # Job functions (packages/worker/jobs.py) pull it back out of `ctx`
    # and open their own request_scoped_session per job — the same
    # per-call session-scoping every background task in this app uses.
    ctx["container"] = ApplicationContainer()
    logger.info("Worker started", queue_prefix=settings.queue.prefix)


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    container: ApplicationContainer | None = ctx.get("container")
    if container is not None:
        engine = container.database.engine()
        await engine.dispose()
    logger.info("Worker shutting down")


class WorkerSettings:
    """
    Real arq worker configuration — replaces the previous `while True:
    sleep(30)` heartbeat, which stayed alive but never did any work
    despite `arq` being a declared dependency the whole time
    (docs/BUILD_STATUS.md's Background Jobs (Phase 12) gap).

    Document ingestion (packages/api/routers/documents.py) now enqueues
    onto this queue as `ingest_document_job`, with real retry (via
    `max_tries` below) on failure — falling back to running in-process
    via FastAPI `BackgroundTasks` only if Redis was unreachable at API
    startup, the same "degrade instead of crash" idiom used for the
    Postgres checkpointer. Memory extraction (packages/api/routers/chat.py)
    deliberately stays on `BackgroundTasks` — it's already proven
    working and doesn't need retry/durability the way a multi-step
    ingestion pipeline does.

    Run via `arq packages.worker.main.WorkerSettings` (arq's own CLI —
    what production/Docker should use, docker/Dockerfile.worker) or
    `python -m packages.worker.main` for local dev, which does the
    same thing through `run_worker()` below.
    """

    functions = [cleanup_orphaned_scratch_files, ingest_document_job]

    cron_jobs = [
        # 4x/day is arbitrary but reasonable for a defense-in-depth
        # sweep — real scratch files should already be gone within
        # seconds of the ingestion that created them finishing.
        cron(cleanup_orphaned_scratch_files, hour={0, 6, 12, 18}, minute=0),
    ]

    redis_settings = ArqRedisSettings.from_dsn(settings.redis.url)

    max_jobs = settings.queue.concurrency
    max_tries = settings.queue.max_retries

    on_startup = _on_startup
    on_shutdown = _on_shutdown


def main() -> None:
    configure_logger(settings.logging.level)
    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
