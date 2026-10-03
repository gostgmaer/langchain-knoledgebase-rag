-- Maps the RAG app's permission-code taxonomy (packages/api/permissions.py) onto IAM's existing
-- super_admin/admin/tenant_admin roles, so turning on the `enable_rbac` feature flag (docs/BUGS.md
-- item 11) doesn't lock any admin out: those three roles are exactly RAGSettings.admin_roles, the
-- set that already passes require_admin() unconditionally on every one of these routes today.
-- Granting all codes to exactly those roles reproduces current access 1:1 — it narrows nothing by
-- itself; a real "read-only operator" role with a subset of codes is a separate, later decision.
--
-- Run against IAM's own database (the `iam` schema on the shared `core-postgres`/`core-pgbouncer`
-- instance), not this app's Postgres:
--   psql -U postgres -d easydev -f scripts/iam_rbac_seed.sql
-- (or, against a Docker-exec'd core-postgres: `docker exec -i core-postgres psql -U postgres -d
-- easydev < scripts/iam_rbac_seed.sql`)
--
-- Idempotent (ON CONFLICT DO NOTHING on both inserts) — safe to re-run after permissions.py adds a
-- new code; rows already granted are left untouched.
--
-- This only maps codes to roles. The `enable_rbac` feature flag itself is a separate, per-tenant,
-- live-editable DB row (packages/domain/models/feature_flag.py) — flip it via the admin Feature
-- Flags page, or `PATCH /api/v1/feature-flags/{id}`, deliberately as its own step, not by running
-- this script.

BEGIN;

INSERT INTO iam.permissions (id, name, description, resource, action, "createdAt")
SELECT gen_random_uuid()::text, code, 'RAG platform permission (langchain-knoledgebase-rag)',
       split_part(code, ':', 1), split_part(code, ':', 2), CURRENT_TIMESTAMP
FROM unnest(ARRAY[
    'agents:read', 'agents:write',
    'analytics:read',
    'documents:read', 'documents:write', 'documents:delete',
    'feedback:read',
    'knowledge_bases:read', 'knowledge_bases:write', 'knowledge_bases:delete',
    'knowledge_sources:read', 'knowledge_sources:write', 'knowledge_sources:delete',
    'knowledge_sources:credentials',
    'models:read', 'models:write',
    'observability:read', 'observability:purge',
    'prompts:read', 'prompts:write',
    'retrieval_logs:read',
    'retrieval_settings:read', 'retrieval_settings:write',
    'tools:read', 'tools:write',
    'upload_jobs:read',
    'usage:read'
]) AS code
ON CONFLICT (name) DO NOTHING;

INSERT INTO iam.role_permissions (id, "roleId", "permissionId", "createdAt")
SELECT gen_random_uuid()::text, r.id, p.id, CURRENT_TIMESTAMP
FROM iam.roles r
CROSS JOIN iam.permissions p
WHERE r.name IN ('super_admin', 'admin', 'tenant_admin')
  AND p.resource IN (
      'agents', 'analytics', 'documents', 'feedback', 'knowledge_bases', 'knowledge_sources',
      'models', 'observability', 'prompts', 'retrieval_logs', 'retrieval_settings', 'tools',
      'upload_jobs', 'usage'
  )
ON CONFLICT ("roleId", "permissionId") DO NOTHING;

COMMIT;

-- Verification: expect 3 roles * 27 permissions = 81 rows.
-- SELECT r.name, count(*) FROM iam.role_permissions rp
--   JOIN iam.roles r ON r.id = rp."roleId"
--   JOIN iam.permissions p ON p.id = rp."permissionId"
--   WHERE p.resource IN ('agents','analytics','documents','feedback','knowledge_bases',
--     'knowledge_sources','models','observability','prompts','retrieval_logs',
--     'retrieval_settings','tools','upload_jobs','usage')
--   GROUP BY r.name;
