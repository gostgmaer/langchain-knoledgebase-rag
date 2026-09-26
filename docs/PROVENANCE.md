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

Audit events (full list in section 11) are each written in their own transaction so they
never join or break the request. Retention (`RETENTION_RETRIEVAL_LOG_DAYS`, default 90;
`RETENTION_AUDIT_DAYS`, default 365; `0` = keep forever) is enforced by a daily worker job
(`purge_expired_logs_job`, 05:00). Documents, versions and chunks are never purged by age.

## 9. What "quality" means here

`observability/summary` reports **health signals** (empty and low-confidence rates, citation coverage). They are
not accuracy. Recall@K / MRR / faithfulness need a labelled question set; `eval/` is the place for it and none
exists yet, so no accuracy improvement is claimed.

## 10. Access control, filters and database-level isolation

* **Per-document access**: `documents.visibility` is `tenant` (every member may retrieve it, the default) or
  `restricted` (administrators only). Set on upload (`visibility=`) or changed with `PATCH /documents/{id}`
  (audited as `document.access_changed`); it applies to the next question, nothing is re-indexed. Enforced **inside
  the retrieval SQL**, so a restricted chunk never leaves the database for a member. The caller's clearance is a
  request-scoped value set by the authentication middleware (`packages/shared/access.py`); it defaults to **no
  clearance** anywhere outside an authenticated request (workers, scripts). Anonymous development mode
  (`AUTH_REQUIRED=false`) keeps the old open behaviour.
* **Metadata filters**: `document_type`, `category`, `tags` (all required), `language`, `knowledge_base_id`,
  `document_ids`. Set on upload (`document_type`, `category`, `tags`) or by `PATCH`; used by `POST /search`
  (`document_types`, `categories`, `tags`, `language`, `knowledge_base_id`) and applied in the search query, not after it.
  Chat does not take filters yet.
* **Conversation ownership**: a conversation is visible only in its own tenant and, within it, to its owner or an
  administrator (`conversation_visible_to`). Everyone else gets 404 (the id's existence is not revealed). This also
  closes a hole where `POST /chat` with another tenant's `conversation_id` was not tenant-checked.
* **Row-level security**: policies on `documents`, `document_chunks`, `embeddings`, `retrieval_logs`,
  `retrieval_result_logs`, `audit_events` restrict rows to `app.tenant_id`, which retrieval sets per transaction
  (`set_config(..., true)`). With it unset (ingestion, workers, migrations) the policy is inactive, so nothing
  else changes. **A PostgreSQL superuser and any `BYPASSRLS` role ignore policies**: in the local compose stack
  the application connects as a superuser, so RLS is *not enforced there*. In production connect as an ordinary
  role (own the tables with a migration role, run the app as a different one). Proven with an ordinary role in
  `tests/integration/test_row_level_security.py`.
* **Score breakdown**: each logged candidate stores its fused score plus the `vector_score` (cosine similarity)
  and `keyword_score` (BM25) that produced it; a candidate found by only one ranker has the other empty.

## 11. Audit events

`document.uploaded`, `document.processed`, `document.version_created`, `document.duplicate_skipped`,
`document.processing_failed` (with the failing stage), `document.reindexed`, `document.viewed` (chunk text
opened), `document.access_changed`, `document.metadata_updated`, `document.deleted`. Retrievals are recorded by
the retrieval log itself.

## 12. Migrations

`alembic upgrade head` now works from an **empty** database and on an existing one (verified on a scratch
database): the baseline revision creates any missing tables, and `7c1d2e9a4b10` adds the columns, indexes and
policies. Both are idempotent and match what the API applies at startup, so use either or both. On an existing
database run `alembic upgrade head` once to record the version.

## 13. Retrieval evaluation

`scripts/evaluate_retrieval.py` scores hit@k, recall@k, precision@k, MRR and NDCG@k for **vector**, **hybrid**
and **hybrid+rerank** on the same questions (`eval/retrieval_eval_set.json`, labelled against the bundled
`eval/corpus`; `scripts/eval_corpus.sh up|down`). First measured run (8 documents, 16 paraphrased questions, k=3):

| mode | hit@3 | recall@3 | MRR | NDCG@3 |
|---|---|---|---|---|
| vector | 1.0 | 1.0 | 1.0 | 1.0 |
| hybrid | 1.0 | 1.0 | 0.9375 | 0.9539 |
| hybrid+rerank | 1.0 | 1.0 | 0.9688 | 0.9769 |

Read this carefully: on this small, easy set every mode finds the right document, and dense-only ranks it first
slightly more often than hybrid. It shows **no benefit from hybrid retrieval or reranking at this scale**; it is
not evidence they are worse in general. A meaningful comparison needs a larger set built from your own
documents, with questions that share little vocabulary with the text and near-duplicate documents.

## 14. Retrieval settings, grants, re-indexing

* **Retrieval settings** (`GET/PUT /retrieval-settings`, UI: *Retrieval settings*): per workspace, how many chunks an
  answer uses (1-20), the reranker score below which weaker chunks are dropped (best chunk always kept), and whether the
  cross-encoder runs. Empty = platform default (`RAG_MAX_RESULTS`, `RAG_MIN_RELEVANCE_SCORE`, `ENABLE_RERANKING`). Applied
  by chat and the multi-agent researcher within ~30 s; audited. With reranking off, chunks are ranked by search score
  and the relevance floor does not apply. The search *strategy* stays platform-wide.
* **Role and user grants**: a restricted document can also be opened to members holding named roles or listed by user id
  (`allowed_roles`, `allowed_users`, set with `PATCH /documents/{id}` or the Access card). Enforced in the retrieval SQL.
* **Chat filters**: `POST /chat` accepts `filters` (`document_types`, `categories`, `tags`, `language`); the chat page has
  a "Limit answers to documents" panel.
* **Re-indexing**: `POST /documents/{id}/reindex` and `POST /documents/reindex-outdated` (buttons on the document page and
  Observability). Runs on the worker with the current pipeline and the chunking strategy the document was uploaded with.
  Re-indexing replaces a document's chunks; earlier answers keep their sources because `message_citations` now snapshots
  document name, page and section and the chunk link is `SET NULL`. (Deleting a document used to leave its chunk rows
  behind and made re-indexing collide with them; both fixed.)

## 15. Running as an ordinary database role (row-level security)

`scripts/create_app_role.sql` creates `rag_app` (no superuser, no BYPASSRLS) with the grants the app needs. Then:
`DATABASE_URL` = `rag_app`, `MIGRATION_DATABASE_URL` = the owner (used by `alembic upgrade head`),
`SCHEMA_INIT_AT_STARTUP=false`. Verified: an API container connected as `rag_app` to an alembic-built database started,
served documents, settings, observability and search, and wrote its own rows without permission errors. The API logs a
warning at startup when its role would bypass row-level security.

## 16. Hybrid weighting (measured)

`RETRIEVAL_KEYWORD_WEIGHT` (default 1.0 = standard reciprocal-rank fusion) scales the BM25 ranking against the dense
ranking. On the bundled 26-question set (k=3, 14 documents including near-duplicate regional policies and
error/product codes), hybrid-without-rerank scored MRR 0.865 / hit 0.92 at weight 1.0, 0.897 / 0.96 at 0.5 and
0.930 / 1.0 at 0.25, while dense-only scored 0.981 / 1.0 and hybrid+rerank 0.936 / 1.0 regardless. Equal weighting let
keyword matches on common words outrank the right document; exact-code queries (`ERR-5023`, `ZX-4420`) were found by
every mode, so this set does not show BM25 helping. The default is unchanged: 26 questions on 14 documents is
direction, not proof. Re-measure on your own documents (`scripts/evaluate_retrieval.py`) before changing it.

## 17. Known gaps

* Access is per document with two levels plus role and user grants; there are no groups or inheritance beyond IAM roles.
* Row-level security is not enforced in the local stack (superuser); the app-role setup in section 15 is what enforces it.
* Documents ingested before provenance existed show "not recorded" until re-indexed (a bulk button exists).
* No `documentVersionId` column: the version is the document row (`document_id`) plus `document_versions`.
* Retrieval-log purge is platform-wide by design; its endpoint is super-admin only.
* Accuracy is only measured on the small bundled set (sections 13 and 16).
