"""
Proves the database itself enforces tenant isolation once a transaction names its tenant.

The application connects as a PostgreSQL superuser in the local compose stack, and superusers
ignore row-level security, so this test does what production must do: reads through an ordinary
role. Everything runs in one transaction that is rolled back.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from packages.config.loader import settings
from packages.infrastructure.database.upgrades import RLS_TABLES, rls_statements


@pytest_asyncio.fixture()
async def connection():
    engine = create_async_engine(str(settings.database.url).replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        conn = await engine.connect()
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"database not reachable: {exc}")
    tx = await conn.begin()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_policies_exist_for_every_tenant_table(connection):
    for statement in rls_statements():
        await connection.execute(text(statement))
    rows = await connection.execute(text("select tablename from pg_policies where policyname = 'tenant_isolation'"))
    assert set(RLS_TABLES) <= {row[0] for row in rows}


@pytest.mark.asyncio
async def test_an_ordinary_role_only_sees_the_tenant_the_transaction_names(connection):
    tenant_a, tenant_b, other = uuid4(), uuid4(), uuid4()
    marker = f"rls-test-{uuid4()}"

    for statement in rls_statements():
        await connection.execute(text(statement))
    for tenant in (tenant_a, tenant_b):
        await connection.execute(
            text(
                "insert into audit_events (id, tenant_id, action, resource_type, detail, is_deleted, created_at, updated_at) "
                "values (:id, :t, :a, 'test', '{}', false, now(), now())"
            ),
            {"id": uuid4(), "t": tenant, "a": marker},
        )

    await connection.execute(text("create role rls_probe nologin"))
    await connection.execute(text("grant select on audit_events to rls_probe"))
    await connection.execute(text("set local role rls_probe"))

    async def visible(tenant) -> int:
        value = "" if tenant is None else str(tenant)
        await connection.execute(text("select set_config('app.tenant_id', :t, true)"), {"t": value})
        result = await connection.execute(text("select count(*) from audit_events where action = :a"), {"a": marker})
        return result.scalar_one()

    assert await visible(tenant_a) == 1
    assert await visible(tenant_b) == 1
    assert await visible(other) == 0  # a tenant with no rows sees nothing, not everything
    assert await visible(None) == 2  # unset (ingestion, workers): policy inactive by design
