"""Provenance columns, access/classification, retrieval logs, audit and row-level security

Revision ID: 7c1d2e9a4b10
Revises: 44b52e61b180
Create Date: 2026-09-26

Applies the same idempotent statements the API runs at startup
(packages/infrastructure/database/upgrades.py), so running this revision, starting the API, or both,
converges on the same schema. New tables come from the baseline's create_all; this revision adds
the columns, indexes and row-level-security policies on top.
"""

from alembic import op
from sqlalchemy import text

from packages.infrastructure.database.upgrades import UPGRADES, rls_statements

revision = "7c1d2e9a4b10"
down_revision = "44b52e61b180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for statement in (*UPGRADES, *rls_statements()):
        bind.execute(text(statement))


def downgrade() -> None:
    # Additive and data-bearing (provenance, audit trail): deliberately not reversible.
    raise NotImplementedError("This revision only adds columns, indexes and policies; it is not downgraded.")
