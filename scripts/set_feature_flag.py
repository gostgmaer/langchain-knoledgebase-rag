"""Create or update a feature_flags row (packages/domain/models/feature_flag.py) via the app's own
ORM/session, so BaseModel's id/timestamp/soft-delete defaults are handled correctly instead of
hand-written in raw SQL — used this session to turn on `enable_rbac` globally (docs/BUGS.md item 11)
after running scripts/iam_rbac_seed.sql against IAM.

Usage (run from the repo root, against whichever DATABASE_URL the environment's .env points at):
    PYTHONPATH=. python scripts/set_feature_flag.py enable_rbac true
    PYTHONPATH=. python scripts/set_feature_flag.py enable_rbac false --tenant-id <uuid>

A tenant_id scopes the row to just that tenant (overriding the global default for it); omitted,
it sets/creates the GLOBAL row (tenant_id IS NULL) that every tenant falls back to.
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from packages.domain.models.feature_flag import FeatureFlag
from packages.infrastructure.container.application import ApplicationContainer
from packages.infrastructure.repositories.feature_flag import FeatureFlagRepository


async def main(key: str, enabled: bool, tenant_id: UUID | None) -> None:
    container = ApplicationContainer()
    session_factory = container.database.session_factory()
    try:
        async with session_factory() as session:
            repo = FeatureFlagRepository(session)
            existing = await repo.get_by_key_and_tenant(key, tenant_id)
            if existing is None:
                flag = await repo.create(
                    FeatureFlag(key=key, tenant_id=tenant_id, enabled=enabled)
                )
                await session.commit()
                print(f"created: key={key} tenant_id={tenant_id} enabled={flag.enabled}")
            else:
                existing.enabled = enabled
                await session.commit()
                print(f"updated: key={key} tenant_id={tenant_id} enabled={existing.enabled}")
    finally:
        engine = container.database.engine()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", help="Feature flag key, e.g. enable_rbac")
    parser.add_argument("enabled", choices=["true", "false"], help="New value")
    parser.add_argument("--tenant-id", type=UUID, default=None, help="Omit for the global row")
    args = parser.parse_args()

    asyncio.run(main(args.key, args.enabled == "true", args.tenant_id))
