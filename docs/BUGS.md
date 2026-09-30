# Known issues — production/enterprise readiness audit

Generated 2026-09-30 from a full read-only audit (security, test coverage/CI, deployment/observability,
feature completeness) run across the whole platform, not just the knowledge-sources connector work.
`docs/BUILD_STATUS.md` and `docs/CHANGELOG.md` remain the authoritative history of *how* things were
built; this file tracks what's still actually wrong, ranked by how much it matters before a real launch.

**Verdict: not production/enterprise-ready yet.** The core chat/RAG/connector pipeline is genuinely
solid and well-tested (382 backend tests, 144 e2e checks, all passing). What's missing is almost
entirely *around* that core: operational safety nets (backups, CI, horizontal scaling), a security
backstop (DB role), and test coverage on the API/frontend surface rather than just the domain logic.

Status legend: 🔴 open · 🟡 in progress · ✅ fixed · 📝 doc-only (code was already fine)

---

## ✅ Fixed this pass

### 0. ✅ Every chat answer whose top citation had a negative rerank score crashed with a 500
- **Found:** not by the audit forks — by a live smoke test run immediately after this pass's other
  fixes, on a completely ordinary chat message. Not a contrived edge case: reranker scores are
  routinely negative (cross-encoder logits), and `RAG_MIN_RELEVANCE_SCORE`'s own docstring says "the
  top chunk is always kept so answers are never left without a citation" — so this fired on a real
  fraction of ordinary chat turns, not a rare corner case.
- **Root cause:** `packages/domain/models/message_citation.py`'s `score` column used to have a
  `CheckConstraint("score >= 0", name="ck_citation_score")`. That was correctly removed from the
  model and a cleanup statement was added to `packages/infrastructure/database/upgrades.py`:
  `ALTER TABLE message_citations DROP CONSTRAINT IF EXISTS ck_citation_score`. But
  `packages/infrastructure/database/metadata.py`'s naming convention
  (`"ck": "ck_%(table_name)s_%(constraint_name)s"`) means `create_all()` actually created that
  constraint in Postgres as **`ck_message_citations_ck_citation_score`**, not the bare declared name.
  The `DROP CONSTRAINT IF EXISTS ck_citation_score` therefore silently no-op'd — `IF EXISTS` never
  raised, so nothing ever surfaced this — on every single API startup since the line was added, and
  the real, stale constraint kept rejecting every citation with a negative score.
- **Fix:** `upgrades.py` now drops the real, convention-prefixed name. Verified live: restarted the
  API through its normal startup path (not a manual DB patch), confirmed the constraint is gone
  (`pg_constraint` query), and re-ran the exact chat request that previously 500'd — now `200`, with
  negative-score citations (`-10.86`, `-11.30`) persisted correctly.
- **Files:** `packages/infrastructure/database/upgrades.py`.

### 0b. ✅ `docker-compose.prod.yml`'s `redis` had no healthcheck despite `api`/`worker` depending on `service_healthy`
Added a real `redis-cli ping` healthcheck, matching the dev compose file. Verified: `docker compose -f
docker-compose.prod.yml config` now validates clean.

### 0c. ✅ Debug `print()` statements in production code, one printing full user message content every chat turn
`packages/conversation/manager.py:72`, `packages/graph/router.py` (6 call sites), and
`packages/tools/builtin/weather.py:160` now use structured `logger.debug(...)` calls instead —
matching the codebase's own established policy (`LoggingMiddleware` never logs message bodies) rather
than just swapping `print` for `logger.debug` with the same content. Verified live: full unit+
integration suite green (382 passed), and a live chat round-trip through the restarted stack.

### 0d. ✅ Misleading stale TODO-stub headers on fully-implemented tool files
Removed the leftover 4–6 line "`# TODO: Define get_weather(location) tool function`"-style scaffold
headers from `packages/tools/builtin/{weather,search,news}.py` — the real implementations below them
were already live-verified working; the headers were only ever misleading.

---

## CRITICAL — blocks a real launch

### 1. 🟡 App connects to Postgres as a superuser in dev, bypassing RLS — real fix documented and proven, not yet the default anywhere
- **Where:** `.env`'s `DATABASE_URL` (`my_db_user`), confirmed live via `select rolsuper` → `t`. This
  is intentional for local/solo dev (lets the schema auto-provision on every boot) — the real gap is
  that no environment, including `docker-compose.prod.yml`, is set up to run any differently.
- **Why it matters:** `packages/infrastructure/database/upgrades.py`'s `rls_statements()` are the
  documented defense-in-depth layer for multi-tenant isolation — a superuser connection bypasses RLS
  policies unconditionally. Tenant isolation without it is enforced **only** by per-repository
  `tenant_id` filters in application code, with **zero database-level backstop** if any one repository
  method ever misses that filter.
- **Fix proven this pass, not yet wired into any deploy path.** `scripts/create_app_role.sql` already
  creates the correct non-superuser `rag_app` role. Live-verified end to end on a disposable scratch
  database: ran the real Alembic migration as the table owner, applied `create_app_role.sql`, booted a
  real API instance connected as `rag_app` with `SCHEMA_INIT_AT_STARTUP=false` — clean startup, no
  RLS-bypass warning, passing health check — and confirmed via raw SQL that RLS genuinely filters rows
  by `app.tenant_id` as `rag_app` (it does not as a superuser). Full account and setup steps now in
  `docs/DEPLOYMENT.md` §4 and `.env.example`.
- **Deliberately not changed:** the shared dev `.env` itself — flipping it to `rag_app` would break
  the schema-auto-provision convenience this whole project's dev workflow (including this session's
  own tooling) depends on. This is scoped as a **production deploy step**, not a local dev default.
  Remains 🟡 rather than ✅ until some real deploy path actually runs it, not just documents it.

### 2. ✅ Architecturally single-replica-only — fixed for the two state stores that were genuinely broken by design
- **Where:** three separate in-memory, per-process state stores were flagged, two of which were
  genuinely a correctness bug under >1 replica:
  - `packages/api/middleware/rate_limit.py`'s `RateLimitMiddleware._hits` — **fixed**: now a
    Redis-backed fixed-window counter (`INCR`+`EXPIRE`, atomic via a pipeline), shared by every
    replica instead of reset-per-process. Verified live: real requests write real, correctly-TTL'd
    keys to Redis, and forcing the counter above the limit correctly returns `429` — this enforcement
    is now genuinely shared across replicas, not per-process. Fails open (not closed) on a Redis
    error, matching the existing "degrade, don't crash" idiom used for the checkpointer/job queue.
  - `packages/memory/manager.py`'s summarize-lock — **fixed**: replaced the in-process
    `dict[UUID, asyncio.Lock]` (which only ever serialized turns handled by the *same* replica, so
    the exact race it was built to close reopened silently under >1 replica) with a real Redis
    distributed lock (`Redis.lock()`, SET NX PX + a release token). Verified live: a real chat turn
    correctly produced exactly one `SUMMARY` memory row via the new lock, no errors.
  - `packages/api/middleware/metrics.py`'s `MetricsStore` — **re-scoped, not actually a bug**: see
    item 10 below. Per-replica metrics are the *correct*, standard Prometheus pattern (each instance
    exposes its own `/metrics`, a real Prometheus server aggregates across replicas at query time),
    not something the app itself needs to solve. The real gap here was that the endpoint wasn't in
    the Prometheus format a real server can scrape at all — now fixed, see item 10.
- Both Redis clients are module-level (matching `packages/tools/builtin/weather.py`'s existing
  pattern) with a `close_*_redis()` hook wired into `lifespan.py`'s shutdown.

### 3. 🟡 No backup/restore strategy for Postgres — scripts built and proven, not yet scheduled anywhere
- **Where:** was confirmed absent — no backup script, no mention in `docs/DEPLOYMENT.md`.
- **Why it matters:** Postgres holds 100% of app data *and* the vector store (when `pgvector` is the
  backend, which it is in this `.env`). No documented DR path meant total data loss on disk failure
  or a bad migration.
- **Fixed this pass:** `scripts/backup_db.sh`/`scripts/restore_db.sh` (real `pg_dump -Fc`/`pg_restore
  --clean --if-exists`, run inside the `postgres` container via `docker compose exec`). Verified live:
  backed up the real dev database (2.4MB, 39 tables), restored it into a disposable scratch container,
  confirmed table count and a real row count matched exactly. Documented in `docs/DEPLOYMENT.md` §5.
- **Still open:** nothing schedules this automatically, and a local dump next to the database it backs
  up doesn't survive that host's disk failing — both are operational decisions for wherever this
  actually deploys (cron cadence, retention, off-host storage target), not something to guess at from
  this repo alone.

### 4. 🟡 No CI pipeline — now added (`.github/workflows/ci.yml`), not yet observed running on real GitHub infrastructure
- **Where:** was confirmed via `git ls-files` — zero `.github/workflows/`, no CI config of any kind.
- **Why it matters:** every one of the 382 passing tests and 144 e2e checks this project has has been
  run manually, locally. Nothing gated a merge or a deploy — a regression could ship silently.
- **Fixed this pass:** `.github/workflows/ci.yml` runs `tests/unit` + `tests/integration` (382 tests)
  against real `pgvector/pgvector:pg17` and `redis:7-alpine` service containers on every push/PR, using
  `uv` for dependency install. No real secrets needed — the test environment is built from
  `.env.example`'s placeholder values plus connection overrides, since the default `pytest` marker
  filter (`-m "not live"`) already excludes the handful of tests needing a real LLM provider key.
- **Verified as thoroughly as possible without triggering real GitHub infrastructure from here**: the
  exact recipe the workflow uses was run locally first — both suites pass 334/334 and 48/48 using only
  `.env.example` values (via a subprocess with its own environment, never touching the real `.env`
  file), and the YAML was parsed to confirm it's syntactically valid and structured as intended. What
  this could **not** verify locally: the real GitHub-hosted runner environment, the service-container
  networking specifics, and whether `uv sync --frozen` succeeds against `uv.lock` on a clean `ubuntu-latest`
  image. Push this and watch the first real run before trusting it fully.
- The `144 e2e checks` (`scripts/e2e_local.sh`/`e2e_sources.sh`) are **not** in this workflow yet — they
  need a running API+worker+frontend stack (`docker compose up`), a heavier CI job than the plain
  pytest suites. Worth a follow-up job, not bundled into this one.

### 5. 🔴 Zero frontend test coverage
- **Where:** `frontend/package.json` has no `"test"` script, no jest/vitest/playwright/cypress
  dependency, 0 test files anywhere under `frontend/`.
- **Why it matters:** the entire UI layer — including the Knowledge Sources wizard walked through
  live this session — is unverified by automation. A backend-safe deploy can still ship a broken UI.

### 6. 🔴 No load/performance testing tooling
- **Where:** no k6/locust/artillery config anywhere in the repo. The only load exercise found is the
  `LOAD_ITEMS` env var in `tests/integration/test_source_sync.py`, which stresses only connector-sync
  bookkeeping, not the real chat/retrieval/embedding pipeline under concurrent users.
- **Why it matters:** no evidence-based answer exists today for "how many concurrent users can this
  handle," which is a basic launch question.

---

## HIGH

### 7. 🔴 `docker-compose.prod.yml` requires a pre-built image nothing in the repo builds
- Requires `easydev/ai-platform:${VERSION}` via Compose's `:?` required-var syntax, but nothing
  builds/tags/pushes that image. `docker compose -f docker-compose.prod.yml up` cannot work standalone.

### 8. ✅ `docker-compose.prod.yml`'s `redis` service was a real Compose config error — see "Fixed this pass" (0b) above.

### 9. 🔴 No zero-downtime deploy story
- `restart: always` + a straight redeploy drops in-flight requests. No reverse-proxy health-gated
  cutover, no rolling-update config.

### 10. ✅ `GET /api/v1/metrics` isn't real Prometheus format
- Was a JSON dump of in-memory counters only, not Prometheus text-format — wouldn't integrate with a
  standard Grafana/Prometheus stack without custom scrape logic.
- **Fixed:** added `prometheus-client` as a real dependency and a new `GET /api/v1/metrics/prometheus`
  route (`packages/api/routers/metrics.py`) returning real Prometheus exposition format via
  `generate_latest()`. New `Counter`/`Histogram` metrics wired into both HTTP request handling
  (`packages/api/middleware/metrics.py`: `http_requests_total`, `http_request_duration_seconds`) and
  graph node execution (`packages/graph/middleware.py`: `graph_node_calls_total`,
  `graph_node_errors_total`, `graph_node_duration_seconds`). The original JSON endpoint is untouched
  (kept as a human-readable convenience view, not replaced).
- Verified live end to end, including through the real auth layer (not bypassed): logged in for a
  real bearer token, called `GET /api/v1/metrics/prometheus` with it, got `200` with
  `content-type: text/plain; version=1.0.0; charset=utf-8`, and confirmed `http_requests_total` was
  genuinely tracking real request traffic with correct `route`/`status` labels (including the
  endpoint's own earlier unauthenticated `401` attempt).

### 11. 🔴 Fine-grained, permission-code RBAC is dead code
- `require_permission()` (`packages/api/dependencies.py:220`) is attached to **zero routes**
  (confirmed via grep), gated behind `ENABLE_RBAC` which defaults `false`. The only real, enforced
  authorization boundary today is the coarser `require_admin()` (admin-or-nothing), used across 14
  routers. Fine for an internal tool; not fine-grained enough for a real multi-tenant enterprise
  launch where different roles need different permissions.

### 12. 🔴 Rate limiting is one flat global limit, not tightened for expensive endpoints
- `RATE_LIMIT_REQUESTS_PER_MINUTE` (default 300/min) applies identically to a health check and to
  `POST /chat` (which triggers an LLM call) or document upload. Compounds with item 2's per-replica bug.

### 13. 🔴 No dependency-vulnerability scanning anywhere
- No `.github/dependabot.yml`, no `pip-audit`/`safety` in `pyproject.toml` or `Makefile`.

### 14. ✅ Debug `print()` statements in production code — see "Fixed this pass" (0c) above.

### 15. ✅ `ModelProfile.provider`/`.model` are stored but never actually read
- Was: `LLMFactory.create()` only ever used the global `settings.ai.default_provider`
  (`docs/CHANGELOG.md:847`). An admin could configure a model profile that claims "uses OpenAI" and
  the app silently kept using the global default instead — a genuine, user-facing correctness gap.
- **Root cause traced further than the original note:** `model_profile_id` was already threaded all
  the way into `GraphState` and even *used* — but only for retrieval settings (`retrieve.py`), never
  for actually selecting which LLM answers. `LLMManager.configure()` (the mechanism that could have
  fixed this) existed but was never called anywhere in the app — confirmed via a full `grep` sweep.
- **Fixed:** `packages/infrastructure/ai/config.py` gained `build_llm_config_from_profile()`, which
  maps a `ModelProfile` row (provider/model/temperature/top_p/top_k/max_tokens) to a real `LLMConfig`
  — falling back to the global default (with a logged warning, not a crash) when the profile names a
  provider `LLMFactory` doesn't implement yet (`ModelProvider` has several values — MISTRAL, OLLAMA,
  OPENROUTER, FIREWORKS, TOGETHER, COHERE, CUSTOM — with no real provider class behind them; building
  those integrations is a separate, much larger gap, not something to paper over here). `LLMNode`
  (`packages/graph/nodes/llm.py`) now resolves `state["model_profile_id"]` through a newly-wired
  `ModelProfileRepository` and passes the result on a new `ChatRequest.llm_config` field.
  `ChatService` (`packages/chat/chat_service.py`) uses it to build a fresh, per-call `LLMManager`
  when set, **never mutating the shared default Singleton** other requests still use — the response's
  own `provider`/`model` fields were also fixed to report the config actually used, not always the
  shared default's (a second, smaller instance of the same "stored but not reflected" bug).
- Required a new `repositories` `DependenciesContainer` on `GraphContainer` (previously not wired in
  at all) — additive DI change, nothing existing repointed.
- **Verified live, both branches:** the default path (unchanged): a real chat call correctly reported
  `model: "gemini-3.1-flash-lite"`, matching the default profile's own stored values (confirmed
  identical to `.env`'s settings first, so this path's output doesn't silently shift). The fallback
  path: created a real model profile via `POST /model-profiles` naming `MISTRAL` (unimplemented),
  pointed a real agent/conversation at it, sent a real message — `200`, correct answer, response
  still reported the working `google`/`gemini-3.1-flash-lite` default, and the exact expected warning
  (`"Model profile references a provider LLMFactory doesn't implement yet"`) appeared in the API
  container's logs. All test data cleaned up afterward.

### 16. 🔴 Most API routers have no router-level HTTP contract test
- `tests/api/` has only 2 files (`test_feature_flags_api.py`, `test_health.py`). 12+ routers —
  `chat`, `conversations`, `documents`, `knowledge_bases`, `search`, `agents`, `models`, `prompts`,
  `tools`, `feedback`, `upload_jobs`, `knowledge_sources` — have no pytest-level route test (status
  codes, schema validation, auth-per-route). Coverage for these comes only from the shell-script e2e
  suites, which aren't CI-discoverable (there is no CI — item 4) and aren't pytest-collected.

### 17. 🔴 No coverage threshold enforced
- `pytest-cov` is a declared dependency; `pyproject.toml`'s `addopts` is just `-m 'not live'` — no
  `--cov`, no `--cov-fail-under`. Coverage is never measured, so regressions in untested code are
  invisible by design.

### 18. 🔴 Connector integration tests have no automatic rollback/isolation
- Unlike `tests/api`/`tests/unit`'s SAVEPOINT-based rollback fixtures, `test_source_sync.py` commits
  real rows and relies on manual cleanup between runs — directly confirmed painful this session (hand
  -written `DELETE FROM ...` needed between live-script runs to avoid stale `identity_mappings`
  causing false failures). Would collide immediately under any future parallel/CI test execution.

---

## MEDIUM

### 19. 🔴 Several packages have no direct unit test file
`packages/services/`, `packages/planner/`, `packages/prompts/`, `packages/worker/`,
`packages/observability/`, `packages/cli.py` — plausibly covered indirectly via integration/e2e paths,
but nothing names them directly.

### 20. 🔴 `packages/application/` — near-zero direct test coverage despite being fully load-bearing
Confirmed genuinely wired into production (`chat.py`, `documents.py`, `observability.py`,
`retrieval_settings.py`, `worker/jobs.py`, `graph/nodes/retrieve.py`, `graph/subgraphs/research.py`
all import it) — not a bug itself, but worth flagging since `docs/BUILD_STATUS.md` still has an old
row calling it "orphaned," which could mislead a future cleanup pass into deleting live code (see the
doc-only section below).

### 21. 🔴 `worker` container has no Docker-level healthcheck
Reasonable for a non-HTTP arq worker, but means Docker/orchestration can't auto-detect or restart a
stuck worker process.

### 22. 🔴 Upload Service `MAX_FILE_SIZE` mismatch (unverified against the real deployed service)
`docs/CHANGELOG.md:563` — this app validates uploads up to 50MB; the real Upload Service's own guide
states a 10MB default. A 20–40MB file could pass local validation and then get a `413` from the real
service. Needs checking against whatever the actually-deployed Upload Service is configured with.

---

## LOW

### 23. ✅ Misleading stale TODO-stub comment headers on fully-implemented files — see "Fixed this pass" (0d) above.

### 24. 🔴 Dead code: `packages/sdk/notification/`
5 real-looking modules (client/email/endpoints/exceptions/models.py); confirmed via
`grep -rl "sdk.notification"` that nothing in `packages/` imports it. Matches
`docs/UNUSED_FILES.md`'s long-standing "safe to remove" recommendation — not removed here since
deletion wasn't explicitly requested.

---

## 📝 Doc-only — code was already fine, `docs/BUILD_STATUS.md` was stale

These aren't bugs; `docs/BUILD_STATUS.md` contained claims that no longer matched the code. Listed
here so they aren't re-"discovered" as bugs later. (Several of these were corrected in this session's
earlier BUILD_STATUS.md edits; the rest surfaced in this pass's audit.)

- "Repository writes no longer commit" — correct by design (commit happens once at the request
  boundary via `request_scoped_session`); the doc's own later text already explains this, an older
  table row just never got removed.
- `packages/infrastructure/ai/factory.py` "orphaned provider factory" — file no longer exists.
- Stale `AgentState` import claims in `packages/conversation/{store,memory_store}.py` /
  `packages/application/application.py` — none of these three files exist anymore.
- `sdk/common/models.py` `NameError: Pagination` — file no longer exists.
- "`packages/application/` orphaned service layer" — directly false today (see item 20 above).
- Security headers gap, vector-store-backend no-op, IAM refresh-token "Partial", Chroma
  auto-start, chat-concurrency session race, real Alembic migrations — all already corrected in
  `docs/BUILD_STATUS.md` earlier this session (see that file's own change history for the account of
  each).

---

## What's actually solid (don't re-litigate these)

- Core chat/RAG/connector pipeline: 334 unit + 48 integration tests, 144 e2e checks, all green.
- Knowledge-sources connectors (SharePoint/OneDrive/Teams/Confluence/Web/Wikipedia): live end-to-end
  proof against purpose-built stand-in servers, including auth, sync, permissions, targeted webhook
  refresh, JS rendering, and citations.
- Credential encryption (Fernet/MultiFernet, real rotation support), SSRF guard
  (`CONNECTOR_ALLOW_PRIVATE_HOSTS` defaults false), no hardcoded secrets in tracked files, sound CORS
  config, no raw-SQL injection found anywhere in `packages/`.
- `AUTH_REQUIRED=true` correctly fails *closed* (503) when IAM is unreachable — only dev mode
  (`AUTH_REQUIRED=false`) fails open, by clear design.
- Real OpenTelemetry tracing, wired end-to-end (not just a stub, despite a stale comment elsewhere
  claiming otherwise).
