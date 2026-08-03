"""
Real Postgres, via the db_session fixture (rolled back after every
test — see tests/conftest.py). FeatureFlag has no FK dependencies, so
it's a clean first integration target for the repository/session layer
itself, distinct from the pure cache-key logic already covered in
tests/unit/test_feature_flag_cache.py.

Every test uses a uuid4()-suffixed `key`, not real flag names like
"enable_rbac" — this dev database has genuine, already-committed rows
from this session's own earlier live verification of the Feature Flags
work, and a query for a real key (e.g. tenant_id IS NULL) would see
both that pre-existing row and whatever this test creates, since a new
transaction sees all previously-committed data under READ COMMITTED.
Confirmed live while writing this file: using "enable_rbac" directly
raised a real `MultipleResultsFound` from exactly that collision.
"""

from uuid import uuid4

import pytest

from packages.domain.models.feature_flag import FeatureFlag
from packages.infrastructure.repositories.feature_flag import FeatureFlagRepository

pytestmark = pytest.mark.integration


def _unique_key() -> str:
    return f"test_flag_{uuid4()}"


@pytest.mark.asyncio
async def test_create_and_get_by_key_and_tenant(db_session):
    repo = FeatureFlagRepository(db_session)
    key = _unique_key()
    tenant_id = uuid4()

    created = await repo.create(FeatureFlag(key=key, tenant_id=tenant_id, enabled=True))
    await db_session.flush()

    fetched = await repo.get_by_key_and_tenant(key, tenant_id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.enabled is True


@pytest.mark.asyncio
async def test_get_effective_prefers_tenant_override_over_global_default(db_session):
    repo = FeatureFlagRepository(db_session)
    key = _unique_key()
    tenant_id = uuid4()

    await repo.create(FeatureFlag(key=key, tenant_id=None, enabled=False))
    await repo.create(FeatureFlag(key=key, tenant_id=tenant_id, enabled=True))
    await db_session.flush()

    assert await repo.get_effective(key, tenant_id) is True
    # A different tenant with no override of its own falls back to the
    # global default.
    assert await repo.get_effective(key, uuid4()) is False


@pytest.mark.asyncio
async def test_get_effective_returns_none_when_no_row_exists_at_all(db_session):
    repo = FeatureFlagRepository(db_session)

    assert await repo.get_effective(_unique_key(), uuid4()) is None


@pytest.mark.asyncio
async def test_list_all_orders_by_key(db_session):
    repo = FeatureFlagRepository(db_session)
    prefix = uuid4()

    await repo.create(FeatureFlag(key=f"zzz_{prefix}", tenant_id=None, enabled=False))
    await repo.create(FeatureFlag(key=f"aaa_{prefix}", tenant_id=None, enabled=False))
    await db_session.flush()

    flags = await repo.list_all(limit=10_000)
    keys = [f.key for f in flags if str(prefix) in f.key]

    assert len(keys) == 2
    assert keys.index(f"aaa_{prefix}") < keys.index(f"zzz_{prefix}")


@pytest.mark.asyncio
async def test_inner_commit_is_only_a_savepoint_not_a_real_commit(container, db_session):
    """
    Proves the db_session fixture's join_transaction_mode="create_savepoint"
    actually works, self-contained rather than relying on test execution
    order: after this test's own `session.commit()` (exactly what
    packages/api/dependencies.py's request_scoped_session does on every
    real request), a genuinely separate connection — its own transaction,
    outside the fixture's savepoint — must not see the row at all, since
    Postgres MVCC never shows one transaction's uncommitted work
    (savepoint or not) to another connection.
    """
    key = _unique_key()
    repo = FeatureFlagRepository(db_session)
    await repo.create(FeatureFlag(key=key, tenant_id=None, enabled=True))
    await db_session.commit()

    engine = container.database.engine()
    async with engine.connect() as outside_connection:
        result = await outside_connection.execute(
            FeatureFlag.__table__.select().where(FeatureFlag.__table__.c.key == key)
        )
        assert result.first() is None
