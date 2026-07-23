from __future__ import annotations

import time
from typing import Any

from packages.config.loader import settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Scratch files are supposed to be deleted right after each document
# upload's background ingestion finishes (packages/api/routers/documents.py's
# `_ingest_in_background`, in a `finally` block) — this is a defense-in-
# depth sweep for anything that survives a crash or a killed process
# mid-ingestion, not the primary cleanup mechanism. An hour is generous:
# real ingestion runs finish in seconds.
_MAX_AGE_SECONDS = 3600


async def cleanup_orphaned_scratch_files(ctx: dict[str, Any]) -> dict[str, int]:
    """
    Deletes any file under `settings.storage.temp_directory` older than
    `_MAX_AGE_SECONDS`. `ctx` is arq's per-job context (Redis pool, job
    id, etc.) — unused here since this job is self-contained, but arq
    always calls job functions with it as the first argument.
    """

    temp_dir = settings.storage.temp_directory

    if not temp_dir.exists():
        return {"checked": 0, "deleted": 0}

    now = time.time()
    checked = 0
    deleted = 0

    for path in temp_dir.iterdir():
        if not path.is_file():
            continue

        checked += 1

        if now - path.stat().st_mtime > _MAX_AGE_SECONDS:
            path.unlink(missing_ok=True)
            deleted += 1
            logger.info("Deleted orphaned scratch file", path=str(path))

    logger.info(
        "Scratch cleanup finished",
        checked=checked,
        deleted=deleted,
    )

    return {"checked": checked, "deleted": deleted}
