from __future__ import annotations

from typing import Any

from arq import cron, run_worker
from arq.connections import RedisSettings as ArqRedisSettings

from packages.config.loader import settings
from packages.shared.logging import configure_logger, get_logger
from packages.worker.jobs import cleanup_orphaned_scratch_files

logger = get_logger(__name__)


async def _on_startup(ctx: dict[str, Any]) -> None:
    logger.info("Worker started", queue_prefix=settings.queue.prefix)


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Worker shutting down")


class WorkerSettings:
    """
    Real arq worker configuration — replaces the previous `while True:
    sleep(30)` heartbeat, which stayed alive but never did any work
    despite `arq` being a declared dependency the whole time
    (docs/BUILD_STATUS.md's Background Jobs (Phase 12) gap).

    Document ingestion and memory extraction deliberately stay on
    FastAPI `BackgroundTasks` (packages/api/routers/documents.py,
    packages/api/routers/chat.py) rather than moving onto this queue —
    both are already built, tested, and verified working this session;
    migrating them here would trade that for durability/retry the
    roadmap doesn't require yet, at real regression risk to something
    that already works. This worker is for genuinely new background
    work instead, starting with a real, if modest, first job.

    Run via `arq packages.worker.main.WorkerSettings` (arq's own CLI —
    what production/Docker should use, docker/Dockerfile.worker) or
    `python -m packages.worker.main` for local dev, which does the
    same thing through `run_worker()` below.
    """

    functions = [cleanup_orphaned_scratch_files]

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
