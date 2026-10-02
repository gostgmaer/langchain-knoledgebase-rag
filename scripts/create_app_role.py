"""
Idempotently creates/updates the restricted `rag_app` Postgres role a real
production deploy should connect as, so row-level security is genuinely
enforced (docs/DEPLOYMENT.md §4, docs/BUGS.md item 1) — a superuser or
BYPASSRLS role ignores every RLS policy unconditionally.

Same statements as scripts/create_app_role.sql, run through psycopg instead
of `psql` so this works inside the application image (no Postgres client
installed there) as the `migrate` one-shot step in docker-compose.prod.yml,
ahead of `api`/`worker` starting.

Connects as the table owner: MIGRATION_DATABASE_URL, falling back to
DATABASE_URL — the exact same precedence
packages/infrastructure/database/migrations.py's `_configure_url()` already
uses for `alembic upgrade head`, so one owner connection string drives both
steps. The role's password comes from APP_DB_PASSWORD, bound as a real query
parameter rather than interpolated into the SQL string.
"""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

from packages.infrastructure.database.utils import to_sync_database_url

# Mirrors scripts/create_app_role.sql exactly, minus the password (set
# separately below via a bound parameter, not a psql :'var' substitution).
STATEMENTS = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_app') THEN
    CREATE ROLE rag_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO rag_app;
GRANT CREATE ON SCHEMA public TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rag_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO rag_app;
"""


def main() -> int:
    password = os.environ.get("APP_DB_PASSWORD")
    if not password:
        print(
            "APP_DB_PASSWORD is not set — refusing to create/update rag_app with no password.",
            file=sys.stderr,
        )
        return 1

    owner_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not owner_url:
        print("Neither MIGRATION_DATABASE_URL nor DATABASE_URL is set.", file=sys.stderr)
        return 1

    # psycopg.connect() wants a plain postgresql:// DSN, not SQLAlchemy's
    # driver-qualified postgresql+psycopg:// scheme.
    conninfo = to_sync_database_url(owner_url).replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(STATEMENTS)
            # ALTER ROLE ... PASSWORD takes a literal in Postgres's own grammar, not
            # a bind parameter (confirmed live: %s there raises "syntax error at or
            # near $1") — sql.Literal still escapes it safely, client-side, rather
            # than interpolating the raw string.
            cur.execute(sql.SQL("ALTER ROLE rag_app PASSWORD {}").format(sql.Literal(password)))

    print("rag_app role is present and its privileges/password are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
