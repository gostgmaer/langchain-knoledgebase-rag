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
    # --- messages: which retrieval supplied the answer's context
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS retrieval_id uuid",
    # citations store reranker logits, which can be negative
    "ALTER TABLE message_citations DROP CONSTRAINT IF EXISTS ck_citation_score",
    # --- indexes for the lookups the admin/observability views make
    "CREATE INDEX IF NOT EXISTS ix_document_tenant_status ON documents (tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_document_checksum ON documents (knowledge_base_id, checksum)",
    "CREATE INDEX IF NOT EXISTS ix_chunk_content_hash ON document_chunks (content_hash)",
    "CREATE INDEX IF NOT EXISTS ix_message_retrieval ON messages (retrieval_id)",
)


async def apply_schema_upgrades(conn: AsyncConnection) -> None:
    for statement in UPGRADES:
        await conn.execute(text(statement))
