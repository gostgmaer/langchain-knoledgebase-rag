# Provenance, retrieval logging and observability

What the RAG platform records about every document, chunk, retrieval and answer, how to read it,
and what is deliberately **not** done yet. Everything here is implemented and covered by
`tests/unit/test_provenance_security.py`, `tests/unit/test_retrieval_log.py`,
`tests/unit/test_chunking_record.py` and section 5c of `scripts/e2e_local.sh`.

## 1. The chain

```
User query
  -> retrieval_logs.id (retrievalId), request_id, trace_id     (one row per retrieval)
  -> retrieval_result_logs   (one row per candidate chunk: search rank/score, reranker score, final rank, used?)
  -> document_chunks         (content_hash, chunking + embedding + pipeline versions, page, section, indexed_at)
  -> documents               (one row per VERSION: is_current, checksum, uploader, parser, pipeline, stage)
  -> document_versions       (root document, version_number, superseded_at)
  -> file_id                 (the original file in the Upload Service)
  -> messages.retrieval_id + message_citations (which answer used which chunks)
```

Correlation ids: `request_id` (per HTTP request, also in every log line), `trace_id` (when tracing is
enabled; empty otherwise), `retrieval_id` (per retrieval), then `document_id` / `chunk_id`. A retrieval log
carries `request_id` and `trace_id`; the answer message carries `retrieval_id`.

## 2. Versions

A re-upload of a file with the same name and **changed** content creates a new `documents` row
(`is_current = true`) and flips the old one to `is_current = false`, with a `document_versions` row. Nothing is
overwritten. **Retrieval only ever returns chunks of a current, `READY`, non-deleted document** - enforced inside
the search SQL (`_retrievable_chunk` in `packages/knowledge/vectorstores/providers/pgvector.py`), so superseded
versions, half-ingested and failed documents never leave the database. (Before this change, superseded versions
stayed searchable.) Old versions stay in the database and in retrieval logs, so a past answer can be traced to
the exact version that produced it.

## 3. Database changes

Applied automatically at API startup by `packages/infrastructure/database/upgrades.py` (idempotent
`ADD COLUMN IF NOT EXISTS`; safe on an existing database, a no-op on a new one). New columns are nullable:
**NULL means "not recorded"** for data that predates them - nothing is invented.

| Table | Change |
|---|---|
| `documents` | `uploaded_by`, `source_type`, `processing_version`, `parser_name`, `chunking_strategy`, `chunking_version`, `embedding_provider`, `embedding_model`, `embedding_dimensions`, `processing_stage`, `error_reason`, `processed_at` |
| `document_chunks` | `content_hash`, `chunking_strategy`, `chunking_version`, `embedding_provider`, `embedding_model`, `embedding_dimensions`, `pipeline_version`, `indexed_at` |
| `messages` | `retrieval_id` |
| `message_citations` | negative-score check dropped (reranker scores are unbounded logits); rows are now actually written |
| **new** `retrieval_logs`, `retrieval_result_logs` | see section 1 |
| **new** `audit_events` | append-only: action, resource, actor, request id, small `detail` JSON (secrets/content keys stripped) |
| indexes | `(tenant_id, status)`, `(knowledge_base_id, checksum)`, `content_hash`, `messages.retrieval_id`, plus per-table lookup indexes on the new tables |

Structured columns hold what is filtered/joined/reported on; JSON (`metadata`) is kept for genuinely dynamic
data (headings, loader output, chunk position).

`alembic/` still has no usable history (see `docs/DEPLOYMENT.md`); the startup upgrade list is the migration
mechanism until that is fixed.

## 4. Ingestion

`load -> clean -> split -> embed -> store`, now tracking a **stage** (`extracting`, `cleaning`, `chunking`,
`embedding`, `indexing`, `completed`). A failure records the stage on the document, prefixes the upload-job error
(`[embedding] ...`) and is retried by the worker as before.

* **Idempotent**: chunk ids are deterministic (`uuid5(document_id, "chunk:<index>")`), so processing the same
  document twice cannot create duplicate chunks.
* **Dedup**: the checksum check ignores failed and superseded documents, so a failed upload can be retried and
  re-uploading old content is a new version, not a "duplicate". Dedup is per knowledge base, never across tenants.
* **Versions recorded**: `PIPELINE_VERSION = ingest-v2`, `CHUNKING_VERSION = chunking-v1`
  (`packages/knowledge/pipelines/ingestion.py`). Bump them when output changes; documents on an older version
  show as "outdated" and count under *Stale embeddings*.
* The embedding provider/model recorded is the configured embedding client's (`EMBEDDING_PROVIDER` /
  `EMBEDDING_MODEL`), not the model profile's chat model.

## 5. Retrieval

`query -> (planner rewrite + expansions) -> tenant-scoped search -> keyword/vector fusion (hybrid retriever)
-> dedupe -> cross-encoder rerank -> relevance floor -> top-k -> delimited context`.

* Every search query filters `embeddings.tenant_id` and model profile **in SQL**, plus the live-document rule above.
* Retrieved text is placed in `<source id="n">` blocks that are described to the model as untrusted data
  (never instructions), with the wrapper tags neutralised inside chunk text; the model is asked to cite `[n]`.
* Each retrieval is logged with its candidates and scores (`retrieval_result_logs`). Only the query **hash and
  length** are stored, never the text. At most 50 candidates are logged per retrieval, and chunks that were used
  are always kept.
* There is no retrieval cache, so there is no cross-tenant cache to leak. If one is added its key must include
  tenant, access scope, query hash and retrieval-config version.

## 6. Answers and citations

`ChatService` persists a `message_citations` row per source and `messages.retrieval_id`. Customer-visible
citation shape (chat response and message history):

```json
{"label": "[1]", "document_name": "Employee Handbook.pdf", "page_number": 12, "section": "Leave Policy"}
```

The chat response still includes `document_id`, `chunk_id`, `chunk_index` and `score` (existing clients use
them). The message-history endpoint (`GET /conversations/{id}/messages`, used by the customer UI) returns **only**
label/name/page/section - no ids, scores or retrieval details. Those are admin-only.

## 7. API (all admin-only unless noted; tenant-scoped)

| Endpoint | Purpose |
|---|---|
| `GET /documents`, `GET /documents/{id}` | now include chunk count, chunking record, provenance and `embedding_is_stale` |
| `GET /documents/{id}/chunks` | every chunk with full text, metadata and provenance columns |
| `GET /retrieval-logs`, `GET /retrieval-logs/{id}` | list retrievals; explain one (candidates, scores, used/dropped, document, version, page, chunking) |
| `GET /observability/summary?days=` | latency avg/p95, empty rate, low-confidence rate, citation coverage, document health, stale embeddings, never-retrieved |
| `GET /observability/top-documents` | most retrieved / most used documents |
| `GET /observability/audit` | audit trail |
| `POST /observability/retention/purge` | run the retention purge now (**super admin**; platform-wide) |
| `GET /conversations/{id}/messages` (any member) | messages plus customer-safe `sources` |

UI (admin and tenant-admin): **Retrieval Log**, **Observability**, document detail (Chunking, Provenance,
Document metadata, per-chunk metadata), knowledge bases (documents with chunking method), chat (sources under
each answer).

## 8. Audit and retention

Audit events are written for document upload accepted and document deleted, each in its own transaction so they
never join or break the request. Retention (`RETENTION_RETRIEVAL_LOG_DAYS`, default 90;
`RETENTION_AUDIT_DAYS`, default 365; `0` = keep forever) is enforced by a daily worker job
(`purge_expired_logs_job`, 05:00). Documents, versions and chunks are never purged by age.

## 9. What "quality" means here

`observability/summary` reports **health signals** (empty and low-confidence rates, citation coverage). They are
not accuracy. Recall@K / MRR / faithfulness need a labelled question set; `eval/` is the place for it and none
exists yet, so no accuracy improvement is claimed.

## 10. Known gaps (not done)

* Audit events cover upload and delete only - not version creation, reindex, access or permission changes.
* No per-document ACLs; access control is tenant + role. Any member of a tenant can read that tenant's
  conversations (`GET /conversations/{id}/messages` checks tenant, not owner).
* The keyword-search score is not broken out from the fused score per candidate (one `retrieval_score` is
  logged); Postgres row-level security is not enabled (isolation is enforced in the query layer and tested there).
* Documents ingested before this change show "not recorded" for provenance; **re-index** them to fill it in.
* No metadata filters (`documentType`, `department`, ...) on the query API yet; no `documentVersionId` column
  (the version is the document row itself - `document_id` - plus `document_versions`).
* Retrieval-log purge is platform-wide by design; the endpoint is super-admin only.
* `alembic` migrations are still not a working history (see section 3).
