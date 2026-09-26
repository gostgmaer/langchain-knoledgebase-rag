# Knowledge sources: external documents in the RAG

Administrators connect external systems (websites, Wikipedia, Confluence, SharePoint, OneDrive, Microsoft Teams);
the platform discovers, versions, chunks, embeds and indexes their content on a schedule, keeps their permissions and
original links, and removes what disappears, all through the **existing** RAG pipeline. Retrieval treats an external
document exactly like an upload; a citation can additionally name the source and link to the original page.

What is verified and how is listed in section 12. Read it: some connectors were tested against a stand-in server, not
the real service.

## 1. Architecture

```
External system
   |  connector  (one class per system; the ONLY code that knows the system)
   v
ExternalDocument (metadata) -> ExternalDocumentContent (text or file bytes)     <- the normalised model
   |  sync engine  (change detection, permissions, bounded parallelism, records, removals)
   v
IngestionRequest  ->  ingestion pipeline  (unchanged: load, clean, split, embed, store)
   v
Document / DocumentVersion / chunks / embeddings   ->   retrieval (unchanged, plus source filters)
```

`packages/connectors/`

| File | Responsibility |
|---|---|
| `models.py` | The normalised model (`ExternalDocument`, `ExternalDocumentContent`, `ExternalPermission`, `ExternalChange`, ...). |
| `base.py` | `BaseKnowledgeConnector` (the contract) and `ConfigField` (a setting; the UI renders forms from these). |
| `registry.py` | `ConnectorRegistry`: type name -> connector class. Everything else asks the registry. |
| `http.py` | The one HTTP client all connectors use: throttling, retries with backoff, `429`/`Retry-After`, timeouts, circuit breaker, SSRF policy, no credential forwarding on cross-host redirects. |
| `html_extract.py` | HTML to clean markdown (drops navigation, banners, ads, scripts; keeps headings, lists, tables, code, links, captions). |
| `credentials.py`, `credential_service.py` | Encryption at rest (Fernet) and the only code that touches a plaintext secret. |
| `access.py` | External permissions to platform access, identity mappings, fail-closed derivation. |
| `sync.py` | The generic sync engine. |
| `scheduling.py` | Creating/dispatching runs, cancellation, the scheduler and the stale-run reaper. |
| `common.py` | Settings every source has (default visibility, permission mode, chunking, bulk-removal guard). |
| `sources/*.py` | `web`, `wikipedia`, `confluence`, `sharepoint` (+`onedrive`), `teams`, and the shared `microsoft_graph` plumbing. |

The pipeline is source-agnostic: it receives an `IngestionRequest` and only *records* the source context it is given
(`source_id`, `source_type`, `external_id`, `canonical_url`, `external_version`, `sync_id`); it never branches on the
source type. Retrieval only gained optional filters.

### Adding a connector

1. Add the type to `SOURCE_TYPES` if it is not there (google_drive, notion, github, gitlab, slack, dropbox, box, jira,
   zendesk, s3, azure_blob, email already are).
2. Subclass `BaseKnowledgeConnector`: `type`, `display_name`, `config_schema` (list of `ConfigField`), `credential_kind` /
   `credential_fields`, then `test_connection`, `discover` (async generator of `ExternalDocument`), `fetch`. Optionally
   `get_changes` (incremental change feed), `get_permissions`, `get_document`.
3. Register it in `sources/__init__.py`.

No change to retrieval, chunking, embedding, the vector store, the LLM, the API or the frontend: the type shows up in
`GET /knowledge-sources/types` and the wizard and configuration forms render from its `config_schema`.
`tests/unit/connectors/test_credentials_registry.py::test_a_new_connector_needs_no_change_outside_its_own_class` proves
the registration path.

## 2. Data model

New tables (all carry `tenant_id`, are covered by the row-level-security policy, and are created at startup and by
alembic):

* `knowledge_sources`: name, type, status (`active|paused|error|disconnected`), sync mode/interval, `last_*` timestamps,
  `configuration` (never secrets), `sync_state` (delta tokens), `health`, webhook secret **hash**.
* `source_credentials`: Fernet ciphertext, kind, key version; unique per source.
* `source_sync_runs`: the sync id, trigger, status, counters, bounded error list, trace/request ids, stats.
* `external_documents`: one row per external item: version, content hash, permissions hash, lifecycle status
  (`discovered|pending|fetching|processing|indexed|updated|deleted|failed`), failure count, link to the current `Document`.
* `document_access_rules`: the normalised external ACL, kept so access can be re-derived when a mapping changes.
* `identity_mappings`: external user/group to internal user/role.

`documents` gained `source_id`, `external_id`, `canonical_url`, `external_version`, `external_updated_at`,
`last_synced_at`, `sync_id` (`source_type` already existed and is now the connector type; uploads are `upload`).
`message_citations` snapshots `source_type`, `source_name`, `canonical_url`, `external_updated_at` so an old answer keeps
its sources even if the source changes.

Provenance chain, as asked: `sync (source_sync_runs.id) -> external document -> document -> document version -> chunk ->
retrieval -> answer`. Every chunk's metadata carries `source_id`, `source_type`, `external_id`, `canonical_url`,
`external_version`, `sync_id` plus the connector's small facts (space key, channel, folder ...).

## 3. Sync semantics

* **Change detection**: an item is skipped, without being fetched, when its external version (revision, etag, eTag,
  version number) equals the stored one. If the version differs but the fetched content hash is the same, nothing is
  re-embedded. Conditional requests (`ETag`/`Last-Modified`) avoid re-downloading pages that did not change.
* **New / updated**: fetch, ingest as a new document version (the previous version stays, marked not current).
* **Renamed / moved**: title, URL or parent changed with identical content: the document's title/link/metadata are updated,
  no re-embedding (counted as `renamed`).
* **Permission change only**: the ACL is updated in place, no re-embedding (`permissions_updated`).
* **Removed at the source**: the document is **archived** (excluded from retrieval, rows/chunks/versions kept), never
  hard-deleted; if the item returns it is restored (or versioned if it changed).
* **Safety nets**: an empty listing never archives anything; a sync that would archive more than half of a source of 20+
  documents is held back unless the source allows it; a discovery failure midway removes nothing.
* **Failures are isolated**: one failing document is recorded (stage, redacted message) and retried next sync; after 5
  consecutive failures it is quarantined until the item changes or an administrator presses Retry.
* **Incremental change feeds** (`get_changes`, used by SharePoint/OneDrive delta): only the change set is processed; the
  delta cursor advances only when everything succeeded.
* **Bounded work**: `CONNECTOR_SYNC_CONCURRENCY` documents at a time, each in its own transaction; progress is flushed to
  the run every 10 documents; a sync can be cancelled between documents.
* **One sync per source at a time** (409 otherwise). A run that stops reporting for 20 minutes is failed by the reaper.

Scheduling: manual, every 15/30 minutes, hourly, daily, weekly. The worker's cron queues due syncs every minute.
Webhook / realtime: `POST /api/v1/webhooks/sources/{id}` with `X-Webhook-Secret` queues a normal sync (a burst becomes one
sync). The secret is shown once and only its hash is stored. Webhook notifications trigger a full (incremental) sync,
not a per-item fetch.

## 4. Permissions

For connectors that read permissions (Confluence page restrictions, SharePoint/OneDrive item permissions, Teams channel
membership) and `permission_mode = sync_external`:

1. The connector returns the item's principals (external ids).
2. `IdentityMapping` turns them into internal users/roles. **External ids are never assumed to equal internal ids.**
3. The document becomes `restricted` with `allowed_roles` / `allowed_users`; an unmapped principal grants nothing, so a
   document whose principals are all unmapped is administrator-only until an admin maps them (Permissions tab).
4. Retrieval enforces this inside the search SQL (the same mechanism as uploads), so unauthorised text never reaches the LLM.

An item with an explicit empty permission list, or a source that reports none, gets the source's default visibility
(`tenant` or `restricted` plus roles). `permission_mode = source_default` ignores external permissions. Changing a
mapping re-derives access for every affected document without contacting the source.

## 5. Credentials and security

* Encrypted at rest with Fernet (`CONNECTOR_CREDENTIAL_KEYS`); no key = nothing can be stored. Stored in their own table,
  scoped by tenant and source and re-checked on every read.
* **Write-only**: `PUT /knowledge-sources/{id}/credentials` sets or rotates; no endpoint returns a secret, only
  `{configured, kind, revoked, updated_at}`. Revoking destroys the ciphertext. Verified against responses, the database
  and the service logs (`scripts/e2e_sources.sh`).
* Errors, run details and logs are passed through a redactor (bearer tokens, `authorization`, `token=`, `secret=`).
* **SSRF**: only `http(s)`; hosts resolving to private, loopback, link-local or metadata addresses are refused unless
  `CONNECTOR_ALLOW_PRIVATE_HOSTS=true`; every redirect hop is re-checked; credentials are dropped on a cross-host redirect
  (pre-signed download URLs). Known limit: name resolution happens twice (check, then connect), so a DNS-rebinding
  attacker controlling a hostname could in theory race it; run the workers with egress restricted at the network layer if
  sources are untrusted.
* Tenant isolation: every query is scoped by `tenant_id`; a source, its runs, records, mappings, webhook and credentials
  are invisible to other tenants (tested at the API and against the database).
* All source endpoints require an administrator; the webhook requires the per-source secret and answers `404` for
  "no such source", "webhooks off", "paused" and "wrong secret" alike.

## 6. Connectors

| Connector | Auth | Discovery | Versioning | Permissions | Notes |
|---|---|---|---|---|---|
| **web** | none | seed URLs + sitemap, BFS by depth/page limits | ETag / content hash | source default | Domain allow-list, include/exclude patterns, robots.txt (Disallow, Crawl-delay, unreadable = skip host), sitemap, canonical URL and content de-duplication, redirects, content-type handling (HTML, text, markdown, PDF), politeness delay. **JavaScript rendering is not available** (needs a headless browser; the setting is rejected). |
| **wikipedia** | none | titles, article URLs, categories (capped) | revision id | public | Official MediaWiki API, descriptive User-Agent, 1 request/second. Stores article id, revision id, language, canonical URL, revision date, categories. |
| **confluence** | email + API token (Cloud) or PAT (Server/DC) | CQL: spaces, exclude spaces, parent pages, labels, content types, archived, personal spaces; optional attachments | page version number | page read restrictions | Bodies via `body.view`; discovery downloads no bodies. Original page URL preserved. |
| **sharepoint** / **onedrive** | Entra app registration (client credentials) or access token | drive **delta** API (libraries, folders, extensions, size, patterns) | eTag | item permissions (users, groups, org-wide links) | Incremental via delta tokens incl. deletions; bytes go through the existing PDF/Word/text loaders. |
| **microsoft_teams** | Entra app registration or access token | standard channels of listed teams (private only if enabled); one document per thread | last modified + reply count | team/channel membership | Never reads chats. Channel messages via application permissions is a Microsoft *protected API* needing Microsoft's approval. |

Planned, not built: Google Drive, Notion, GitHub, GitLab, Slack, Dropbox, Box, Jira, Zendesk, S3, Azure Blob, Email.
They are named in `SOURCE_TYPES`, listed as "coming soon", and need only a connector class.

## 7. API (administrators; tenant-scoped)

`GET /knowledge-sources/types` | `GET /knowledge-sources/summary` | `POST /knowledge-sources/test` (unsaved config) |
`POST|GET /knowledge-sources` | `GET|PATCH|DELETE /knowledge-sources/{id}` | `PUT|DELETE /{id}/credentials` |
`POST /{id}/test-connection` | `POST /{id}/preview` | `POST /{id}/sync` | `POST /{id}/sync/cancel` | `POST /{id}/pause|resume` |
`GET /{id}/runs`, `/{id}/runs/{run}` | `GET /{id}/documents` | `POST /{id}/documents/{record}/retry` | `GET /{id}/health` |
`GET /{id}/permissions` | `GET|PUT /identity-mappings`, `DELETE /identity-mappings/{id}` | `POST /api/v1/webhooks/sources/{id}`.

Retrieval: `POST /search` and `POST /chat` (`filters`) accept `sources` (types) and `source_ids`. `GET /documents` accepts
`source_id`. Citations gain `source_type`, `source_name`, `url` (the original page/file; never an internal API URL),
`updated_at`; the customer message history shows the same and still no internal ids or scores.

## 8. Admin UI

Knowledge Sources (dashboard: sources, attention needed, documents/chunks, today's added/updated/removed, last sync time;
source cards with status, documents, last/next sync, Sync now / Configure / Pause) - Add source wizard (select, connect,
test, select content, permissions, schedule, review, start; **nothing is ingested until the last step**, which previews
first) - Source detail (overview and health, configuration, sync history with per-run errors, documents with freshness
and Retry, permissions and identity mappings). Documents and the document page show the source, URL, version and
freshness; chat shows source links; chat/search accept a "sources" filter. Forms are generated from each connector's
`config_schema`.

## 9. Observability

Every sync has a `syncId` (also on each document and chunk), the `traceId`/`requestId` of the request that started it,
counters, duration and API stats (requests, retries, errors, rate-limit hits and usage %). Audit events:
`source.created`, `updated`, `deleted`, `credentials_connected`, `credentials_revoked`, `sync_requested`, `sync_started`,
`sync_completed`, `sync_stopped`, `sync_failed`, `content_selection_changed`, `permissions_changed`,
`documents_indexed`, `documents_removed`. The retrieval log names the source of each candidate.

## 10. Failure behaviour

A failing source never affects others: each sync is its own job, documents fail individually, the HTTP client retries
transient errors with backoff and opens a per-host circuit after repeated failures, and a source whose credentials are
rejected is marked **disconnected** (other failures mark it **error**) while uploads, web and every other source keep
working.

## 11. Setup

Set `CONNECTOR_CREDENTIAL_KEYS` (and `CONNECTOR_ALLOW_PRIVATE_HOSTS` if a source is on a private network) in `.env`
(docs/ENVIRONMENT.md 3.4a), restart the API and worker, open **Knowledge Sources**. Existing databases pick up the new
tables and columns at startup (or `alembic upgrade head`). Running the API as a non-superuser role: re-run
`scripts/create_app_role.sql` so it is granted the new tables.

## 12. Verification: what is and is not proven

* `tests/unit/connectors` (79 tests): HTTP client (retry, backoff, 429/Retry-After, breaker, throttle, SSRF, redirect
  credential stripping), HTML extraction, the web crawler (scope, patterns, depth, robots, sitemap, canonical/duplicate,
  conditional GET, content types, failures, cancel), Wikipedia, Confluence, SharePoint/OneDrive/Teams, credential
  encryption and rotation, the registry.
* `tests/integration/test_source_sync.py` (19 tests, real Postgres, scripted connector): create/skip/update/version/rename/
  remove/restore, failure isolation and quarantine, empty-listing and bulk-removal guards, cancellation, incremental
  changes, permission derivation, fail-closed ACLs, identity mappings, credential scope.
* `scripts/e2e_sources.sh` (64 checks, real API + worker): a documentation website served in a container, crawled,
  answered from with citations, changed/removed/restored, scheduled, webhooked, credentials never leaking, tenant
  isolation.
* **Live against the real service:** the web crawler (own test site) and Wikipedia (the real MediaWiki API).
* **Against a stand-in server, not the real service:** Confluence (a mock of its REST API, including authentication,
  restrictions, versions), and SharePoint, OneDrive and Teams (unit tests with recorded-shape Graph responses). Their
  request and response shapes follow the official documentation but have **not** been exercised against a real Confluence
  or Microsoft 365 tenant; expect to adjust field names or permissions on first contact, and verify with the Test
  connection button and a Preview before the first sync.
* Not built: JavaScript-rendered pages, the planned connectors, per-item webhook events (a webhook triggers a sync), and
  attachments/shared files for Teams.
* Lifecycle: an external item is recorded as `indexed`, `updated`, `deleted` or `failed`. `discovered`, `pending`,
  `fetching` and `processing` exist as values but are not written mid-flight, because each document is processed in one
  transaction (progress is visible through the run's counters instead).
* Scale: designed for many sources and large ones (metadata-only discovery, version comparison before any fetch, bounded
  parallelism, per-document transactions, indexes on tenant/source/status), but **not load-tested** beyond a few hundred
  documents. Concurrency limits are per sync (`CONNECTOR_SYNC_CONCURRENCY`) and per worker (arq `max_jobs`); there is no
  global per-tenant cap across sources, and the per-document record lookup is one query each.
