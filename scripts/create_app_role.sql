-- Creates the ordinary (non-superuser) database role the application should connect as in production,
-- so PostgreSQL row-level security (tenant isolation, see docs/PROVENANCE.md) is actually enforced:
-- superusers and BYPASSRLS roles ignore every policy.
--
-- Run once as the table owner / a superuser, inside the application database:
--   psql -U <owner> -d <database> -v app_password='<strong password>' -f scripts/create_app_role.sql
--
-- Then: connect the app as rag_app (DATABASE_URL), keep the owner for migrations
-- (MIGRATION_DATABASE_URL=<owner url>; `alembic upgrade head`), and set SCHEMA_INIT_AT_STARTUP=false.
-- Re-run after new tables are added (it is idempotent); default privileges cover tables the owner
-- creates from now on.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_app') THEN
    CREATE ROLE rag_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;

ALTER ROLE rag_app PASSWORD :'app_password';

GRANT USAGE ON SCHEMA public TO rag_app;
-- The LangGraph checkpointer runs `CREATE TABLE IF NOT EXISTS` at startup, which PostgreSQL authorises
-- against the schema even when the table exists. Remove this grant if you run the checkpointer setup
-- as the owner instead.
GRANT CREATE ON SCHEMA public TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rag_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO rag_app;
