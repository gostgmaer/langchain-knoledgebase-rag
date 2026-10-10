"""
Idempotent schema upgrades applied at startup, after `Base.metadata.create_all`.

`create_all` only creates missing tables; it never adds a column to a table that already
exists, and this project has no working Alembic history (see docs/DEPLOYMENT.md). Every
statement here is safe to run repeatedly, so an existing database is brought up to the current
models without data loss and a fresh one is a no-op. New columns are nullable: NULL means
"not recorded" for rows that predate them.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

UPGRADES: tuple[str, ...] = (
    # --- documents: provenance and processing record
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS uploaded_by uuid",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_type varchar(32)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_version varchar(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS parser_name varchar(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunking_strategy varchar(32)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunking_version varchar(32)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_provider varchar(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model varchar(128)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_dimensions integer",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_stage varchar(32)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS error_reason text",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processed_at timestamptz",
    # --- document_chunks: provenance
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content_hash varchar(64)",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunking_strategy varchar(32)",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunking_version varchar(32)",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_provider varchar(64)",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_model varchar(128)",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_dimensions integer",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS pipeline_version varchar(64)",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS indexed_at timestamptz",
    "ALTER TABLE retrieval_result_logs ADD COLUMN IF NOT EXISTS vector_score double precision",
    "ALTER TABLE retrieval_result_logs ADD COLUMN IF NOT EXISTS keyword_score double precision",
    # --- documents: external source provenance and freshness
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_id uuid",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS external_id varchar(1024)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS canonical_url text",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS external_version varchar(256)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS external_updated_at timestamptz",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS last_synced_at timestamptz",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS sync_id uuid",
    "CREATE INDEX IF NOT EXISTS ix_document_source ON documents (tenant_id, source_id)",
    "CREATE INDEX IF NOT EXISTS ix_document_external ON documents (source_id, external_id)",
    # citations snapshot where an answer's source lives, so history survives a source change
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS source_type varchar(32)",
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS source_name varchar(200)",
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS canonical_url text",
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS external_updated_at timestamptz",
    # --- documents: classification and access
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS visibility varchar(16)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_type varchar(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS allowed_roles jsonb",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS allowed_users jsonb",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS category varchar(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS tags jsonb",
    "CREATE INDEX IF NOT EXISTS ix_document_type ON documents (tenant_id, document_type)",
    # --- messages: which retrieval supplied the answer's context
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS retrieval_id uuid",
    # citations store reranker logits, which can be negative. The declared CheckConstraint name was
    # "ck_citation_score", but packages/infrastructure/database/metadata.py's naming_convention
    # ("ck": "ck_%(table_name)s_%(constraint_name)s") means create_all() actually created it in
    # Postgres as ck_message_citations_ck_citation_score - dropping the bare name was a silent
    # no-op (IF EXISTS never raised) on every startup since this line was added, so the stale
    # constraint kept rejecting every citation with a negative rerank score. Confirmed live via
    # pg_get_constraintdef before fixing this.
    "ALTER TABLE message_citations DROP CONSTRAINT IF EXISTS ck_message_citations_ck_citation_score",
    # citations survive a re-index: chunk link becomes SET NULL, and the reader-facing facts are snapshotted
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS document_name varchar(512)",
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS page_number integer",
    "ALTER TABLE message_citations ADD COLUMN IF NOT EXISTS section varchar(512)",
    "ALTER TABLE message_citations ALTER COLUMN chunk_id DROP NOT NULL",
    "DO $$ BEGIN "
    "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_message_citations_chunk_id_document_chunks' "
    "AND confdeltype = 'n') THEN "
    "ALTER TABLE message_citations DROP CONSTRAINT IF EXISTS message_citations_chunk_id_fkey; "
    "ALTER TABLE message_citations DROP CONSTRAINT IF EXISTS fk_message_citations_chunk_id_document_chunks; "
    "ALTER TABLE message_citations ADD CONSTRAINT fk_message_citations_chunk_id_document_chunks "
    "FOREIGN KEY (chunk_id) REFERENCES document_chunks (id) ON DELETE SET NULL; "
    "END IF; END $$",
    "UPDATE message_citations mc SET document_name = d.file_name, page_number = c.page_number, section = c.section "
    "FROM documents d, document_chunks c "
    "WHERE mc.document_name IS NULL AND d.id = mc.document_id AND c.id = mc.chunk_id",
    # --- indexes for the lookups the admin/observability views make
    "CREATE INDEX IF NOT EXISTS ix_document_tenant_status ON documents (tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_document_checksum ON documents (knowledge_base_id, checksum)",
    "CREATE INDEX IF NOT EXISTS ix_chunk_content_hash ON document_chunks (content_hash)",
    "CREATE INDEX IF NOT EXISTS ix_message_retrieval ON messages (retrieval_id)",
    # --- agents: public embeddable chat widget (docs/BUGS.md item 37)
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS widget_enabled boolean NOT NULL DEFAULT false",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS widget_public_id varchar(32)",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS widget_allowed_origins json NOT NULL DEFAULT '[]'",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_widget_public_id ON agents (widget_public_id) WHERE widget_public_id IS NOT NULL",
    # model_profiles.provider: was a native Postgres enum (uppercase labels only), which rejected
    # any caller sending a differently-cased but valid provider name (e.g. "google") with a raw DB
    # error instead of a clean 422 — validation now lives at the API boundary instead, case-
    # insensitively, so the column just needs to hold whatever string the caller sent. Safe to
    # rerun: ALTER COLUMN TYPE to the type a column already has is a no-op.
    "ALTER TABLE model_profiles ALTER COLUMN provider TYPE varchar(50) USING provider::text",
    # model_profiles.is_default: nothing enforced "exactly one default profile" — create/update
    # could mark a second profile as default with no error, and get_default()'s `.limit(1)` with no
    # deterministic ordering would then silently pick either one, each call independently (confirmed
    # live: two profiles both ended up is_default=true via ordinary PATCH calls). Application code
    # now clears every other profile's flag before setting a new default (packages/infrastructure/
    # repositories/model_profile.py's clear_default(), called from packages/api/routers/models.py),
    # but a database that already has duplicates from before this fix needs cleaning up before the
    # new unique index below can be created. Keeps the oldest duplicate; arbitrary but deterministic,
    # and no worse than the pre-existing nondeterministic .limit(1) behavior (docs/BUGS.md item 39).
    "UPDATE model_profiles SET is_default = false "
    "WHERE is_default = true "
    "AND id <> (SELECT id FROM model_profiles WHERE is_default = true ORDER BY created_at ASC, id ASC LIMIT 1)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_model_profile_single_default ON model_profiles (is_default) WHERE is_default = true",
    # memories: "one SUMMARY row per conversation" was an application-level invariant only — no DB
    # constraint backed it. MemoryManager.summarize()'s Redis lock guarded the check-then-act, but
    # its critical section was released before the transaction that actually persisted the create
    # was committed (commit happens later, at the caller's own session boundary), so two calls
    # close together could still both see "no row yet" and both insert one. The repository's own
    # get_by_conversation_and_type() already tolerated this defensively (picks the most-recently-
    # updated row rather than crashing on a duplicate), so this was never a crash in practice — just
    # silent duplicate rows accumulating. Fixed at the source with a real atomic upsert
    # (packages/infrastructure/repositories/memory.py's upsert_summary()); this cleans up any
    # duplicates a pre-fix database already has (keeps the most recently updated one per
    # conversation, same tie-break the repository's own defensive read already used) before the
    # unique index it needs can be created.
    "DELETE FROM memories m USING memories m2 "
    "WHERE m.type = 'SUMMARY' AND m2.type = 'SUMMARY' "
    "AND m.conversation_id = m2.conversation_id "
    "AND (m.updated_at, m.id) < (m2.updated_at, m2.id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_conversation_summary ON memories (conversation_id, type) WHERE type = 'SUMMARY'",
    # One active (queued/running) sync run per source: packages/connectors/scheduling.py's
    # create_run() used to rely solely on a check-then-insert (SELECT active runs, then INSERT) with
    # no row lock, so two concurrent callers (a manual "sync now" double-click, a scheduled sync
    # racing a webhook notification) could both pass the check and both insert a queued run. This
    # index gives create_run() something atomic to conflict against instead. Cleans up any existing
    # duplicates first (cancels every active run but the most recently updated one per source), same
    # tie-break as the memory-summary cleanup above, so the index can actually be created.
    "UPDATE source_sync_runs r SET status = 'cancelled', completed_at = now() "
    "FROM source_sync_runs r2 "
    "WHERE r.status IN ('queued', 'running') AND r2.status IN ('queued', 'running') "
    "AND r.source_id = r2.source_id "
    "AND (r.updated_at, r.id) < (r2.updated_at, r2.id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_source_sync_runs_active ON source_sync_runs (source_id) WHERE status IN ('queued', 'running')",
)

# Row-level security: defence in depth behind the query-layer tenant filters. The policy applies
# only once a transaction has said which tenant it serves (`app.tenant_id`, set by retrieval);
# with it unset - ingestion, workers, migrations - behaviour is unchanged. FORCE makes it apply to
# the table owner too. NOTE: a PostgreSQL SUPERUSER (and roles with BYPASSRLS) ignores every policy,
# so enforcement needs the application to connect as an ordinary role (docs/PROVENANCE.md).
RLS_TABLES = (
    "documents",
    "document_chunks",
    "embeddings",
    "retrieval_logs",
    "retrieval_result_logs",
    "audit_events",
    "knowledge_sources",
    "source_credentials",
    "source_sync_runs",
    "external_documents",
    "document_access_rules",
    "identity_mappings",
)

_TENANT_MATCH = (
    "NULLIF(current_setting('app.tenant_id', true), '') IS NULL "
    "OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
)


def rls_statements() -> list[str]:
    statements: list[str] = []
    for table in RLS_TABLES:
        statements += [
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
            f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
            f"CREATE POLICY tenant_isolation ON {table} USING ({_TENANT_MATCH})",
        ]
    return statements


async def apply_schema_upgrades(conn: AsyncConnection) -> None:
    for statement in (*UPGRADES, *rls_statements()):
        await conn.execute(text(statement))
