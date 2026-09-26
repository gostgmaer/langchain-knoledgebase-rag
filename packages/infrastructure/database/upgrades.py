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
    # citations store reranker logits, which can be negative
    "ALTER TABLE message_citations DROP CONSTRAINT IF EXISTS ck_citation_score",
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
