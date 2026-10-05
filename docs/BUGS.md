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

### 1. ✅ App connects to Postgres as a superuser in dev, bypassing RLS — now wired into a real deploy path by default
- **Where:** `.env`'s `DATABASE_URL` (`my_db_user`), confirmed live via `select rolsuper` → `t`. This
  is intentional for local/solo dev (lets the schema auto-provision on every boot) — the real gap was
  that no environment, including `docker-compose.prod.yml`, was set up to run any differently.
- **Why it matters:** `packages/infrastructure/database/upgrades.py`'s `rls_statements()` are the
  documented defense-in-depth layer for multi-tenant isolation — a superuser connection bypasses RLS
  policies unconditionally. Tenant isolation without it is enforced **only** by per-repository
  `tenant_id` filters in application code, with **zero database-level backstop** if any one repository
  method ever misses that filter.
- **Fixed this pass — closes the gap the previous pass left open ("proven, not yet wired into any
  deploy path").** `docker-compose.prod.yml` now has a one-shot `migrate` service that runs
  `alembic upgrade head` (as the table owner, via `MIGRATION_DATABASE_URL`) and a new
  `scripts/create_app_role.py` (creates/updates the restricted `rag_app` role — the same statements as
  `scripts/create_app_role.sql`, run via `psycopg` so no `psql` client is needed inside the image) —
  and `api`/`worker` now both declare `depends_on: migrate: condition: service_completed_successfully`,
  so a plain `docker compose -f docker-compose.prod.yml up` genuinely can't start the app ahead of RLS
  being enforced. Full setup now in `docs/DEPLOYMENT.md` §4 and `.env.example`
  (`MIGRATION_DATABASE_URL`/`APP_DB_PASSWORD`, new).
- **A real bug found and fixed while building this:** `ALTER ROLE rag_app PASSWORD %s` with a bound
  psycopg parameter failed outright (`psycopg.errors.SyntaxError: syntax error at or near "$1"`) —
  Postgres's own grammar for `ALTER ROLE ... PASSWORD` takes a literal, not a bind parameter. Fixed
  with `psycopg.sql.Literal`, which still escapes the password safely client-side rather than
  interpolating the raw string, just not through the wire-protocol parameter mechanism.
- **Verified live, inside the real application image** (not a bare-host Python process): ran the exact
  `migrate` command (`alembic upgrade head && PYTHONPATH=. python scripts/create_app_role.py`) in a
  container from this project's own built image, against a disposable scratch Postgres. Confirmed
  `rag_app` has exactly the privileges normal operation needs, a real login as `rag_app` reports
  `rolsuper = f`/`rolbypassrls = f`, and re-ran the same command a second time to confirm it's
  genuinely idempotent. `docker compose -f docker-compose.prod.yml config` validates the new
  `depends_on`/`service_completed_successfully` wiring is syntactically correct.
- **Not yet observed:** a full `docker compose -f docker-compose.prod.yml up` run exercising the real
  `migrate`→`api`/`worker` startup ordering end to end (verified piecewise above — the command in the
  real image, and the compose graph's validity — but not that exact sequence together under a real
  `up`), and the shared dev `.env` is deliberately still untouched (flipping it to `rag_app` would
  break the schema-auto-provision convenience local dev depends on) — this was always scoped as a
  production deploy concern, not a local dev default.

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

### 3. ✅ No backup/restore strategy for Postgres — now scheduled automatically, not just manual scripts
- **Where:** was confirmed absent — no backup script, no mention in `docs/DEPLOYMENT.md`.
- **Why it matters:** Postgres holds 100% of app data *and* the vector store (when `pgvector` is the
  backend, which it is in this `.env`). No documented DR path meant total data loss on disk failure
  or a bad migration.
- **Fixed, scripts:** `scripts/backup_db.sh`/`scripts/restore_db.sh` (real `pg_dump -Fc`/`pg_restore
  --clean --if-exists`, run inside the `postgres` container via `docker compose exec`). Verified live:
  backed up the real dev database (2.4MB, 39 tables), restored it into a disposable scratch container,
  confirmed table count and a real row count matched exactly.
- **Fixed this pass, closes the scheduling gap:** `docker-compose.prod.yml` gained a `backup`
  sidecar (new `scripts/backup_db_scheduled.sh`) — same image as `postgres` (so its bundled
  `pg_dump` always matches the server's major version), connecting directly over the `backend`
  network rather than a docker-socket mount (pg_dump is read-only; no reason to grant a backup
  sidecar that much privilege). Loops on a real interval (`BACKUP_INTERVAL_SECONDS`, default
  daily), pruning dumps older than `BACKUP_RETENTION_DAYS` (default 14) each cycle.
- **Verified live**: ran a disposable instance of the sidecar (15s interval, for a fast test) against
  the real dev database over the compose network — a real 2.8MB dump landed within a second, and
  `pg_restore --list` against it confirmed 313 real, valid TOC entries (not a corrupt/empty file).
  Documented in `docs/DEPLOYMENT.md` §5.
- **Still open, genuinely an operational decision, not guessed at here:** `backups-data` is a volume
  on the *same host* as `postgres-data` — this closes "nothing schedules it," not "survives that
  host's disk failing." Shipping dumps off-host (S3, a remote volume, an rsync step) needs a real
  target, which only whoever operates the actual deployment can specify.

### 4. ✅ No CI pipeline — now added and observed running on real GitHub infrastructure, which caught two real bugs the local-only verification missed
- **Where:** was confirmed via `git ls-files` — zero `.github/workflows/`, no CI config of any kind.
- **Why it matters:** every one of the 382 passing tests and 144 e2e checks this project has has been
  run manually, locally. Nothing gated a merge or a deploy — a regression could ship silently.
- **Fixed:** `.github/workflows/ci.yml` runs `tests/unit` + `tests/integration` (382 tests) against
  real `pgvector/pgvector:pg17` and `redis:7-alpine` service containers on every push/PR, using `uv`
  for dependency install. No real secrets needed — the test environment is built from
  `.env.example`'s placeholder values plus connection overrides, since the default `pytest` marker
  filter (`-m "not live"`) already excludes the handful of tests needing a real LLM provider key.
- **First real run (PR #3) failed, and correctly so** — the "verified locally" claim below turned out
  to be a genuine false positive, for the same category of mistake as item 26's `/tmp`-mount bug:
  looked solid against an environment that wasn't actually a clean slate.
  - **`dependency-audit` failed**: `pip-audit` found real, unignored CVEs — `urllib3` 2.7.0
    (PYSEC-2026-4175/4176/4177, fixed in 2.8.0) and `virtualenv` 21.6.1 (PYSEC-2026-4011/4012/4013/
    4014, fixed in 21.7.x+). Both are transitive, not direct `pyproject.toml` pins. Fixed by
    `uv lock --upgrade-package urllib3 --upgrade-package virtualenv` (urllib3 → 2.8.0, virtualenv →
    21.14.5); `pip-audit` with the same ignore list now reports zero vulnerabilities, verified
    locally.
  - **`test` failed**: `asyncpg.exceptions.UndefinedTableError: relation "knowledge_sources" does not
    exist` in `tests/integration/test_source_sync.py`. Root cause: nothing in the CI job ever created
    the schema. `tests/conftest.py`'s fixtures deliberately skip the app's `lifespan()` (and therefore
    its `create_all()`/`apply_schema_upgrades()` auto-provisioning) — correct for route tests, but it
    means the schema has to already exist. On every local dev machine it already does (from a prior
    `docker compose up`); on CI's brand-new ephemeral Postgres container it never did. The local
    "verified" run below was against a dev Postgres with leftover schema from normal day-to-day use,
    not a genuinely empty one — the same trap, just in CI config instead of a shell script. Fixed by
    adding a `uv run alembic upgrade head` step (the same command `docker-compose.prod.yml`'s
    `migrate` service runs, §4 above) before the test steps. **Verified live**: reproduced the exact
    failure first (disposable scratch Postgres, confirmed zero tables, confirmed the same
    `UndefinedTableError`), then ran the new migration step against it (confirmed `knowledge_sources`
    now exists) and re-ran the previously-failing test file, which passed.
- The `144 e2e checks` (`scripts/e2e_local.sh`/`e2e_sources.sh`) are **not** in this workflow yet — they
  need a running API+worker+frontend stack (`docker compose up`), a heavier CI job than the plain
  pytest suites. Worth a follow-up job, not bundled into this one.

### 5. ✅ Zero frontend test coverage — a real harness now exists, not exhaustive coverage
- **Was:** `frontend/package.json` had no `"test"` script, no jest/vitest/playwright/cypress
  dependency, 0 test files anywhere under `frontend/`.
- **Why it matters:** the entire UI layer — including the Knowledge Sources wizard walked through
  live earlier this session — was unverified by automation. A backend-safe deploy could still ship
  a broken UI.
- **Fixed:** Vitest + React Testing Library (`frontend/vitest.config.mts`), with real tests for
  `lib/utils.ts` and two presentational components (`StatusBadge`'s status→variant mapping,
  `ChunkingBadge`'s requested-vs-actual label logic) — not stubs. 29 tests, all passing, 100%
  coverage of the files they touch. Wired into `.github/workflows/ci.yml` as a new `frontend-test`
  job (type-check + `pnpm test`) alongside the backend jobs.
- **Scope, stated honestly:** this establishes the harness and pattern, not exhaustive coverage of
  every component — a realistic scope for one pass given the size of the original gap.

### 6. ✅ No load/performance testing tooling — now real, run live, and it immediately found a genuine capacity issue
- **Was:** no k6/locust/artillery config anywhere in the repo. The only load exercise found was the
  `LOAD_ITEMS` env var in `tests/integration/test_source_sync.py`, which stresses only connector-sync
  bookkeeping, not the real chat/retrieval/embedding pipeline under concurrent users.
- **Fixed:** `loadtest/k6_baseline.js` — a real k6 script against this app's actual API (health +
  authenticated document-list + a real search request exercising the full embedding/hybrid-search/
  rerank pipeline), with latency/error-rate thresholds as real pass/fail criteria, not just traffic
  generation. `loadtest/k6_chat_smoke.js` is a separate, deliberately tiny single-request script for
  a full chat round trip (real LLM generation) — kept apart so a routine load-test run never
  silently racks up provider costs. `loadtest/README.md` documents how to get k6 (a standalone
  binary, not an npm/pip package) and a real bearer token.
- **Run live against this dev stack at 15 concurrent users (a modest, realistic number) — and it
  surfaced a genuine, previously-unknown capacity constraint on the first try**: 76.6% of requests
  failed. Not backend capacity — `RATE_LIMIT_EXPENSIVE_REQUESTS_PER_MINUTE` (default 60/min) and
  `RATE_LIMIT_REQUESTS_PER_MINUTE` (default 300/min) are both keyed on `X-Tenant-ID`
  (`packages/api/middleware/rate_limit.py`), meaning **one shared 60-req/min budget for an entire
  tenant's chat/search/upload traffic combined, not per-user**. Confirmed directly: a plain request
  right after the run returned a real `429`. This is the rate limiter correctly doing its job (item
  12), not a bug — but it's a genuine, concrete answer to this item's own question ("how many
  concurrent users can this handle"): as few as ~10 people in one tenant each sending one message a
  minute would already hit that ceiling. Full writeup in `loadtest/README.md`.
- **Not done**: a follow-up run with the rate limit raised/disabled to find the *next* real ceiling
  (backend/DB capacity) — changing that in a live environment is a deliberate operational decision
  for whoever actually deploys this, not something to flip silently while building the tooling.
- **Why it matters:** no evidence-based answer exists today for "how many concurrent users can this
  handle," which is a basic launch question.

---

## HIGH

### 7. ✅ `docker-compose.prod.yml` requires a pre-built image nothing in the repo builds
- Was: requires `easydev/ai-platform:${VERSION}` via Compose's `:?` required-var syntax, but nothing
  in the repo built/tagged/pushed that image.
- **Fixed:** `scripts/build_prod_image.sh <version>` builds `docker/Dockerfile` once and tags it as
  `easydev/ai-platform:<version>`, matching what the compose file expects (`api`/`worker` already
  share one image); `PUSH=1` also pushes it. Documented in `docs/DEPLOYMENT.md` §6.
- **Verified live this pass**, once this environment's persistent build-network issue (the same one
  blocking items 13/21 — large `torch` download) cleared on its own: ran the script for real
  (`scripts/build_prod_image.sh 0.1.0-test`), got a clean `docker build` (2.79GB image), confirmed
  via `docker images`, then removed the test tag again (never pushed — it was only ever for
  verification, not a real release).

### 8. ✅ `docker-compose.prod.yml`'s `redis` service was a real Compose config error — see "Fixed this pass" (0b) above.

### 9. ✅ No zero-downtime deploy story — built for real, the reverse-proxy + blue-green option
- Was: `restart: always` + a straight redeploy drops in-flight requests. No reverse-proxy
  health-gated cutover, no rolling-update config.
- **A previous pass deliberately left this undone**, documenting three real options rather than
  picking one unasked (reverse proxy + blue-green; an orchestrator with rolling updates built in;
  accept brief downtime as a legitimate choice). **This pass built the first option.**
- **Fixed:** `docker-compose.prod.yml`'s single `api` service is now `traefik` (the only public
  entrypoint) plus `api_blue`/`api_green` — two identical replicas of one logical Traefik service,
  neither publishing a host port directly. Traefik discovers backends via Docker and automatically
  routes only to containers whose Docker `HEALTHCHECK` reports healthy (already baked into
  `docker/Dockerfile`, no extra config needed for that part). New `scripts/deploy_blue_green.sh`:
  starts the idle color on the new version, waits for it to go healthy (Traefik routes to *both*
  colors during this window — the actual zero-gap mechanism), then drains and stops the old one.
  Rolls back automatically (stops the new color, leaves the old one running) if the new color
  never goes healthy within `HEALTH_TIMEOUT_SECONDS`.
- **This relies on item 2's fix being real, not assumed**: running two `api` replicas side by side
  is only safe because `RateLimitMiddleware` and the memory summarize-lock are genuinely
  Redis-backed and cross-replica-safe now — confirmed by re-checking item 2 before building this,
  not just trusting its own "Fixed" marker. `docs/DEPLOYMENT.md`'s §3 had a stale warning against
  running more than one `api` replica, left over from before item 2's fix — corrected in the same
  pass as this one, not left contradicting it.
- **Verified**: `docker compose -f docker-compose.prod.yml config` resolves cleanly — correct
  labels, no port publish on `api_blue`/`api_green`, `traefik`'s command/port/socket-mount config
  all render as intended. `scripts/deploy_blue_green.sh` passes `sh -n`. **Full live verification
  deferred** — this environment's Docker Desktop was down for this pass; a real `VERSION=x` →
  `VERSION=y` deploy watching requests succeed throughout hasn't been observed yet.

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

### 11. ✅ Fine-grained, permission-code RBAC is dead code — taxonomy proposed, wired, mapped on the IAM side, and deliberately turned on
- `require_permission()` (`packages/api/dependencies.py:220`) was attached to **zero routes**
  (confirmed via grep), gated behind `ENABLE_RBAC` which defaults `false`. The only real, enforced
  authorization boundary was the coarser `require_admin()` (admin-or-nothing), used across 14
  routers.
- **Re-read closely the previous pass:** this wasn't an oversight — `require_permission()`'s own
  docstring says it's deliberately gated off "since the real IAM integration... hasn't been verified
  end-to-end with real credentials yet." The mechanism itself was already fully implemented and
  correct (`401` with no user, `403` without the permission code, a real no-op while the flag is
  off) — what was missing was a **permission-code taxonomy** (what codes exist, which roles get
  which) and real IAM credentials to verify enforcement against. Deliberately not invented
  silently in that pass — attaching codes to 14+ routers is a real product/security decision.
- **This pass, with the user's explicit go-ahead to propose a taxonomy**: added
  `packages/api/permissions.py` — a `Permission` class of `<resource>:<action>` string constants
  (read/write/delete per router, matching each router's URL prefix), with a module docstring
  explaining the scope rules (additive on top of `require_admin()`, never a replacement; most
  resources get read/write/delete; a couple get one extra, narrower code where one specific action
  is genuinely higher-risk than the rest of that resource's writes —
  `knowledge_sources:credentials` for rotating/revoking a connector's real external secret,
  `observability:purge` for the platform-wide retention-delete route, which already had its own
  separate `require_super_admin()`). Wired a matching `Depends(require_permission(...))` onto every
  route previously gated only by `require_admin()` across all 14 routers (documents and
  knowledge_sources — the two largest and most sensitive — got full per-route read/write/delete/
  credentials granularity; smaller, uniformly-admin routers got one code per resource).
- **`feature_flags` deliberately excluded, not an oversight**: that router manages the `enable_rbac`
  flag itself, and `require_permission()`'s enforcement is gated by that same flag — stacking a
  permission-code check on the very router that controls it risks locking an admin out of ever
  turning `enable_rbac` back off once it's on. Documented inline in
  `packages/api/routers/feature_flags.py`; it keeps `require_admin()` as its only guard.
  `feedback`'s public submit route (`POST /feedback`) also deliberately gets no code — only the
  admin-only review route does; submitting feedback stays open to any authenticated user, unchanged.
- **Verified live**: full unit+integration suite (383) and the separate `tests/api` suite (7) both
  green. A real import of `packages.api.app` confirms every router still wires up with no error.
  Restarted the real running dev API container (picks up the new code, volume-mounted) — clean
  startup, no tracebacks. With `ENABLE_RBAC` at its real default (`false`), loaded the live
  Knowledge Sources and Documents admin pages as a real logged-in admin — both render real data
  exactly as before, confirming the new `require_permission()` dependencies are genuinely inert
  no-ops today, not a behavior change.
- **Closed out this pass**: mapped all 27 permission codes (`packages/api/permissions.py`) onto IAM's
  `super_admin`/`admin`/`tenant_admin` roles — the exact set `RAGSettings.admin_roles` already lets
  through `require_admin()` on every one of these routes — via idempotent `INSERT ... ON CONFLICT DO
  NOTHING` statements against `iam.permissions`/`iam.role_permissions` directly (same
  `docker exec core-postgres psql` access pattern used elsewhere this session). Granting all 27 codes
  to exactly the roles that already have full access reproduces current behavior 1:1; it doesn't
  narrow anything yet; (a real "read-only operator" role is a separate, later product decision).
  Then created the global `enable_rbac` feature-flag row (`enabled=true`) via the app's own ORM, not
  hand-written SQL, so `FeatureFlag`'s id/timestamp defaults are handled correctly.
- **Verified live, end to end, through the real auth layer**: logged in as the bootstrap super admin
  via the real gateway, confirmed `GET /auth/me` now returns the new RAG codes
  (`agents:read`, `documents:write`, `knowledge_sources:credentials`, `observability:purge`,
  `usage:read` all present) alongside the ~157 other platform permissions, confirmed via
  `GET /api/v1/feature-flags` that the running API's own view of `enable_rbac` is `true` (not just
  the DB row), and confirmed `GET /api/v1/agents` and `GET /api/v1/knowledge-sources` both still
  return `200` with a real admin token — RBAC is genuinely enforcing now (not a no-op), and no admin
  was locked out.

### 12. ✅ Rate limiting is one flat global limit, not tightened for expensive endpoints
- Was: `RATE_LIMIT_REQUESTS_PER_MINUTE` (default 300/min) applied identically to a health check and
  to `POST /chat` (an LLM call) or document upload.
- **Fixed:** a second, tighter cap (`RATE_LIMIT_EXPENSIVE_REQUESTS_PER_MINUTE`, default 60/min)
  layered on top of the general one, for `/chat`, `/search`, and `POST /documents` specifically
  (`packages/api/middleware/rate_limit.py`'s `EXPENSIVE_ROUTES`) — a request to one of those still
  counts against the general limit too, it just also has its own, stricter per-tenant/IP bucket.
  Both buckets are independent Redis counters (same fixed-window mechanism as item 2's fix), so this
  correctly compounds with, not conflicts with, the per-replica fix above.
- **Verified live** (no rebuild needed — `rate_limit.py` is volume-mounted, a restart was enough):
  forced the `expensive` bucket over its limit for one tenant via Redis, then confirmed a real
  `POST /chat` for that tenant got `429` while a real `GET /health` for the *same* tenant still
  returned `200` — proving the two buckets are genuinely independent, not just the general limit
  firing early. Full unit+integration suite (382) and `e2e_local.sh` (80) both still green afterward.

### 13. ✅ No dependency-vulnerability scanning anywhere
- Was: no `.github/dependabot.yml`, no `pip-audit`/`safety` anywhere.
- **Fixed:** added `pip-audit` as a real dev dependency and a `dependency-audit` job in
  `.github/workflows/ci.yml`, running on every push/PR — real enforcement (fails the build), not
  just reporting.
- **Found real, current vulnerabilities running it — 36 across 8 packages — and fixed what could
  actually be fixed**, rather than just wiring up the scanner and leaving known issues in place:
  patch/minor-version bumps for `aiohttp` (3.14.1→3.14.3), `cryptography` (49.0.0→50.0.1),
  `langgraph-checkpoint-postgres` (3.1.0→3.1.2), `pyjwt` (2.13.0→2.15.1), `pypdf` (6.14.2→6.19.0),
  and `soupsieve` (2.8.4→2.10); a major-version bump for the transitive `oauthlib` (3.3.1→4.0.0,
  resolved cleanly with no conflicts). Down to 5 known vulnerabilities in 1 package: `chromadb`
  1.5.9, confirmed live against PyPI to already be the latest version — no fix exists yet, a genuine
  upstream-pending issue, not something fixable from this side. The CI job explicitly
  `--ignore-vuln`s only those 4 specific chromadb CVE IDs (each one named, not a blanket suppression)
  so it still fails on anything new.
- **Verified live**: full unit+integration suite (382) green after all the bumps; `e2e_local.sh` (80,
  including the Google OAuth authorize-redirect check that exercises the bumped `oauthlib`) also
  green. `docker compose ps`-level container verification blocked by the same persistent build
  network issue as item 21 — the dependency changes themselves are correct and tested at the
  source/host level (`uv sync` resolved and installed everything cleanly), just not yet re-baked
  into the running image.

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

### 25. 🔴 `scripts/e2e_local.sh`'s test documents leave orphaned rows other pages surface to real users, not just clutter
- **Found** during a frontend admin-nav audit, not a targeted investigation: the Observability page's
  "Most retrieved documents" table was showing raw truncated document IDs instead of names for 248 of
  415 `retrieval_result_logs` rows (60%). Traced via direct SQL to rows referencing `document_id`s with
  no matching row in `documents` at all — both the frontend (`observability-view.tsx`) and backend
  (`observability.py`'s real `LEFT OUTER JOIN`) were already correct; the data itself was wrong.
  Dated across this whole session's e2e-script testing window, all `e2e_doc_*`/`e2e_restricted_*`
  named documents created by `scripts/e2e_local.sh`.
- **Why it matters beyond test hygiene (the gap item 18 already tracks for connector tests):** this
  isn't just stale rows slowing down a later test run — it's test data a real admin would see as a
  visibly broken table in a production-adjacent environment any time these e2e scripts run against a
  shared, non-ephemeral database. The same `e2e_doc_*`/`e2e_restricted_*` documents are still visible,
  un-archived, inside real Knowledge Base cards today (confirmed live: the `default` KB's "+22
  archived/superseded" count includes several of them).
- **Fixed this pass:** the 248 orphaned `retrieval_result_logs` rows were deleted directly via SQL
  (a data fix, restoring Observability's accuracy today), and the Knowledge Base card was changed to
  filter to current/non-archived documents so leftover test docs stop being visually indistinguishable
  from real content (`docs/CHANGELOG.md`'s "enterprise-grade UI" entry). Neither fix touches the root
  cause.
- **Not fixed — the root cause:** `scripts/e2e_local.sh` has no equivalent of
  `test_source_sync.py`'s manual cleanup discipline (itself inadequate, per item 18) and creates
  documents through the real API (so they generate real dependent rows: chunks, retrieval logs) with
  no teardown step at all. Needs either a real teardown pass at the end of the script (delete-by-prefix
  on its own `e2e_*` naming convention, cascading to dependent tables) or point the script at a
  disposable database the way `tests/integration` already does — not something to bolt on silently
  while fixing an unrelated frontend item.

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

### 21. ✅ `worker` container has no Docker-level healthcheck
- Was: reasonable for a non-HTTP arq worker, but meant Docker/orchestration couldn't auto-detect or
  restart a stuck (not crashed — a crash already triggers `restart: unless-stopped` on its own,
  since the worker is the container's only process) worker.
- **Fixed:** `arq` has a real, built-in health-check mechanism (`record_health()` refreshes a Redis
  key every `health_check_interval`; `arq <settings> --check` reads it back and exits 0/1) — no need
  to hand-roll one. `packages/worker/main.py`'s `WorkerSettings` sets `health_check_interval = 60`
  (arq's own default is 3600s, too long for a responsive Docker healthcheck), and
  `docker/Dockerfile.worker` has a real `HEALTHCHECK` running `arq
  packages.worker.main.WorkerSettings --check`.
- **A second real bug found and fixed this pass, once the image could finally be rebuilt** (the
  previous pass's build-network blocker cleared — see item 7): the `HEALTHCHECK`'s own
  `--timeout=10s` was too short for the command it runs. `arq ... --check` imports
  `packages.worker.main` — and transitively the whole RAG/ML dependency chain (torch, transformers,
  etc.) — before it ever reaches Redis, measured live at ~18s inside this exact image. The 10s
  timeout made Docker report a genuinely healthy worker as `unhealthy` forever: `docker inspect`'s
  health log showed `"Health check exceeded timeout (10s)"` on every single attempt, while running
  the identical command directly (untimed) succeeded in ~18s every time. Fixed by bumping both
  `--timeout` and `--start-period` to 30s.
- **Verified live, end to end, closing the exact gap the previous pass left open**: rebuilt the
  worker image for real (`docker compose build worker`), recreated the container, and watched it
  transition through Docker's own health states — confirmed via `docker inspect` and
  `docker compose ps worker`, which now genuinely reports `Up ... (healthy)`, not just a correctly-
  written but unobserved `HEALTHCHECK` directive.

### 22. ✅ Upload Service `MAX_FILE_SIZE` mismatch — checked against the real, actually-running service, not guessed
`docs/CHANGELOG.md:563` — this app validated uploads up to 50MB; the real Upload Service's own guide
states a 10MB default. A 20–40MB file could pass local validation and then get rejected by the real
service.
- **Checked, not a crash/bug (previous pass):** `packages/api/routers/documents.py`'s upload route
  already catches `SDKException` from the Upload Service call and surfaces its real rejection
  message as a clean `400`, not a generic/opaque error. A rejected-for-size upload fails cleanly
  with the real service's own message, just later than ideal (after the full file already reached
  this app) — this part was already fine and is unchanged.
- **Fixed for real this pass**: the real Upload Service happens to be running locally in this
  environment (`file-upload-service`), so — rather than continuing to guess from a doc comment —
  read its actual source directly: `config/index.js:53` is
  `maxFileSize: _int(process.env.MAX_FILE_SIZE, 10485760)` (10MB), and its container's real env
  (`docker exec file-upload-service printenv`) confirmed `MAX_FILE_SIZE` is **not** set, i.e. it
  genuinely is running at that 10MB default today, not some higher value this app couldn't know
  about. `packages/config/storage.py`'s `StorageSettings.max_file_size` default changed from 50MB to
  10MB to match, with a comment citing exactly how this was verified (not a repeat of the original
  doc-comment guess) and how to override it (`MAX_FILE_SIZE`) if the real service is ever
  reconfigured with a higher limit. `.env.example` updated to match.

### 26. ✅ Secrets in `.env` — no Docker secrets, no external secrets manager integration
`docs/DEPLOYMENT.md` §3 flagged this: genuinely sensitive values (API keys, DB passwords, connection
strings) sat in plain-text `.env` alongside ordinary non-sensitive config, with no separation between
the two in production.

- **Fixed:** `docker-compose.prod.yml` now has a real Docker-secrets mechanism (file-based `secrets:`,
  works with a plain `docker compose up`, no Swarm required) covering 21 genuinely sensitive values —
  database/cache credentials, auth/crypto secrets, and every LLM-provider/tool-integration API key.
  Consolidated into **one** `KEY=value` file (`secrets/app.env`, mounted as a single Docker secret)
  rather than one file per key — nothing in Compose's `secrets:` mechanism requires a 1:1 split, and
  one file is meaningfully less setup friction than twenty. `scripts/docker_secrets_entrypoint.sh`
  (new) parses that file line-by-line with `read` (not `.`/`source` — see the bug below) before
  exec'ing the service's actual command, so `packages/config/*.py` needed zero changes.
  `postgres_password` stays a separate single-value secret (the official postgres image's native
  `POSTGRES_PASSWORD_FILE` support expects a raw value, not `KEY=value` lines); `postgres` mounts it
  directly, `backup` reads the same password back out of `app.env` via the wrapper. Full mechanism
  and setup steps in `secrets/README.md` and `docs/DEPLOYMENT.md` §8; `secrets/app.env.example` and
  `secrets/postgres_password.txt.example` are tracked, the real `secrets/app.env` and
  `secrets/postgres_password.txt` are gitignored.
- **A real bug found and fixed while consolidating to one file**: the first version of
  `docker_secrets_entrypoint.sh` loaded `app.env` by sourcing it (`. /run/secrets/app_env`), which
  runs each line as a shell assignment — a value containing `$` gets misparsed as a variable
  reference (confirmed: a password like `p@ss$w0rd` crashed with `w0rd: unbound variable`), and a
  value containing backticks or `$(...)` would execute arbitrary commands as the container's entrypoint,
  not just fail. Fixed by parsing line-by-line with `read` instead, which treats each line as inert
  text; confirmed via standalone shell tests that `$`, backticks, and `$(...)` inside a secret value
  now all come through completely literally.
- **Verified live** (original per-file design), inside the real application image against a
  disposable scratch Postgres: mounted fake secret files (one containing special characters, to rule
  out a quoting bug) alongside a deliberately-wrong `-e DATABASE_URL=...`/
  `-e MIGRATION_DATABASE_URL=...` override on the container itself, and confirmed the resolved
  environment used the secret-file value, not the wrong `-e` override — i.e. the mechanism genuinely
  takes precedence rather than merely being present. `alembic upgrade head` and
  `scripts/create_app_role.py` (item 1) both then ran successfully using that resolved value. The
  consolidated single-file version's parsing logic was re-verified via standalone shell tests only
  (Docker Desktop was down this pass) — a fresh full-container re-run is still worth doing before a
  real production deploy. `docker compose -f docker-compose.prod.yml config` also resolves cleanly with
  no real `*.txt` files present.

---

## LOW

### 23. ✅ Misleading stale TODO-stub comment headers on fully-implemented files — see "Fixed this pass" (0d) above.

### 24. ✅ Dead code: `packages/sdk/notification/`
Deleted (5 files: client/email/endpoints/exceptions/models.py) — re-confirmed zero references
anywhere (`grep -rl "sdk.notification"` across `packages/`/`tests/`) before removing.
`docs/UNUSED_FILES.md` corrected alongside it (four other listed files turned out to already be
gone too, from an earlier pass — that table just never got updated).

### 27. ✅ Full-shell "Loading…" flash on every hard navigation — looked like 3 inconsistent pages, was actually one gate
A full end-to-end UI audit (every admin page visited, console checked, one real action tried per
page) found Documents/Analytics/Observability flashing a totally blank page — no sidebar, no
topbar — while loading, when every other route kept the app shell and showed an in-content
skeleton instead.
- **Root cause**: `app-shell.tsx`'s session gate (`if (isLoading || !session || ...) return
  <div>Loading…</div>`) blanks the *entire* shell, not just the content area, and runs on every
  hard navigation (the audit used full browser navigations, not in-app `Link` clicks) — on *every*
  page, not just these 3. It was only catchable on screen for pages slow enough to still be in
  that state when a screenshot landed (Documents' heavier table, Analytics'/Observability's chart
  rendering) — not a per-page inconsistency, the same gate everywhere, just differently visible.
- **Fixed:** `Sidebar`/`Topbar` never actually depend on session data (`navItems`/`homeHref` come
  from the `[role]` URL segment, not the session), so they now render immediately and
  unconditionally; only the `<main>` content area swaps to a skeleton while the session resolves.
  `topbar.tsx`'s own `if (!session) return null` had the same problem one level down (the header
  bar itself would vanish and reflow back in) — now renders its `<header>` shell unconditionally
  too, with a skeleton for the session-dependent parts only.
- Also found during the same audit and fixed: Chat's conversation header showed a raw ID
  (`Conversation 903fbec1…`) instead of a title, inconsistent with the history sidebar, which
  already showed a readable preview for the same conversation (`useConversationHistory`'s local
  index). The header now reads from the same `entries` list instead of the id.
- **Verified live**: full-stack UI audit (22 pages, every console checked, one real action per
  page — chat message, search query, connector wizard, etc.) found zero console errors/warnings
  across the board; this fix and the Upload Jobs list below (item 28) were then re-verified live
  individually — screenshot of Chat showing a real conversation's title, confirmed console clean.

### 28. ✅ Upload Jobs had no list view — paste-an-ID lookup only
The same UI audit: `UploadJobsView` was a bare "paste the upload_job_id" box with the page's own
description admitting "the backend has no list-all endpoint for these."
- **Not actually true** — `UploadJobRepository.list_by_tenant()`/`count_by_tenant()` already
  existed, unused; only the router endpoint, schema, and frontend list view were missing.
- **Fixed:** `GET /api/v1/upload-jobs` (paginated, tenant-scoped, most-recent-first) using the
  existing repository methods; `UploadJobListResponseSchema` to match. Frontend: `useUploadJobs()`
  hook (polls every 3s only while something in the page is still `QUEUED`/`RUNNING`, same idea as
  the existing per-job poll), and `UploadJobsView` rewritten as a real table with the existing
  `EmptyState`/`StatusBadge`/`QueryError` conventions — the ID-lookup box stays as a secondary
  "jump to a specific job" affordance, not the only way in.
- **Verified live**: `GET /api/v1/upload-jobs` with a real admin token returned all 74 real upload
  jobs in this environment; loaded the page in a real browser, confirmed the table renders with
  correct status badges and timestamps, confirmed zero console errors.

### 29. ✅ CUSTOM tool definitions were disconnected from the real tool registry — now real, callable webhook tools
The same UI audit: `ToolsView`'s own description admitted a DB-backed `Tool` row was "distinct
from the in-process registry that actually powers chat tool-calling" — creating one did nothing
real; built-in tools (calculator, weather, search, knowledge-base search, IAM lookups) were the
only ones chat could ever actually call.
- **Scope, deliberately bounded** (user's own call, asked explicitly rather than invented): only
  CUSTOM-category tools get real execution, as a generic HTTP webhook — the LLM's single text
  input is sent to `configuration.url`. The other 8 categories (SEARCH, DATABASE, API, FILE, EMAIL,
  NOTIFICATION, AI, UTILITY) already have fixed, code-defined implementations in
  `packages/tools/builtin/`; a DB row in one of those stays descriptive metadata, same as before —
  a generic per-category execution engine for all of them is a separate, much larger decision.
- **Fixed:** `packages/tools/webhook.py`'s `make_webhook_tool()` builds a real LangChain
  `StructuredTool` from a `Tool` row, reusing `packages/connectors/http.py`'s
  `ResilientHttpClient` — the same SSRF-safe, retrying, circuit-broken client every knowledge
  source connector already uses — rather than a second, weaker HTTP path. `CONNECTOR_ALLOW_PRIVATE_
  HOSTS` governs both, so the policy is one setting, not two.
- **A real architectural constraint surfaced and solved, not glossed over**: `ApplicationContainer`
  is one shared, process-wide instance (not rebuilt per request), and the whole LangGraph graph —
  nodes, LLM tool-binding, all of it — is built through a fully *synchronous*
  `dependency-injector` provider chain (`packages/infrastructure/container/graph.py`). Registering
  a tenant's custom tools needs an async DB query; making `init_tool_manager` itself async would
  have forced every one of a dozen-plus providers up the chain (and every caller of
  `container.graph.*` anywhere in the app) to become async too — a blast radius far bigger than
  this feature. Fixed with a narrow `ContextVar` (`packages/tools/context.py`, same pattern
  `current_session` already uses for the identical structural reason): the chat router does the
  async DB fetch and builds the real tool objects up front (`load_custom_tools()`), drops them in
  the context var, and the synchronous `init_tool_manager` just reads them back — zero async code
  added anywhere in the DI chain.
- **Verified live, fully end to end**, not just unit-level: created a real CUSTOM tool via
  `POST /api/v1/tool-definitions` (`configuration: {"url": "https://httpbin.org/post"}`), sent a
  real chat message asking the model to call it — the LLM genuinely recognized and chose to call
  it (`pending_approval.tool_calls[0].name == "say-pong"`), approved the pending tool call via
  `POST /chat/{id}/resume`, and the webhook actually executed and the model used the real response
  ("PONG"). Separately confirmed the SSRF guard itself: `assert_public_url()` correctly blocked
  `169.254.169.254` (cloud metadata), `127.0.0.1`, `localhost`, and `192.168.1.1` when called
  directly; the live webhook call to a metadata-style address only timed out instead of being
  blocked because this *dev* environment has `CONNECTOR_ALLOW_PRIVATE_HOSTS=true` (same setting
  connectors already read) — production's default `false` blocks it the same way connectors are
  already blocked today. Full unit+integration suite (385) still green.

### 30. ✅ Prompts had no text or version history UI — the data model was already there, unused
The same UI audit: `PromptsView`'s own description admitted "actual prompt text/versioning has no
UI yet." Creating a prompt only ever created metadata (name/category/description) — there was no
way to give it real content at all.
- **Not actually a missing data model** — `PromptVersion` (`packages/domain/models/prompt_version.py`)
  already existed, fully designed: `template` (the real text), incrementing `version`, `status`
  (DRAFT/PUBLISHED/DEPRECATED/ARCHIVED), `is_published`, `changelog`, `variables`, `examples`. It
  just had zero repository methods, zero API routes, and zero frontend UI — the same
  "already-built, never wired up" shape as item 28 (Upload Jobs).
- **Fixed:** `PromptVersionRepository` (list/get-published/next-version-number/publish);
  `GET /prompts/{id}/versions` (full history), `POST /prompts/{id}/versions` (new DRAFT),
  `POST /prompts/{id}/versions/{version_id}/publish`. Publish is the one operation that does the
  real work: it unpublishes whichever version was live (demoting its status to DEPRECATED) and
  publishes the target — the exact same operation whether the target is the newest draft or an
  older version, which is what makes "rollback" not a special case: it's just publishing an old
  version again. Nothing is ever deleted or overwritten. `PromptResponseSchema` now carries
  `published_version` inline so the list page shows current live content without a second request.
  Frontend: a "Versions" panel per prompt with the full history, a new-draft form, and a Publish
  button per non-live version.
- **Verified live, the full cycle**: created a real prompt, created v1 and published it, created v2
  and published it (confirmed v1 auto-demoted to DEPRECATED), then **rolled back** by publishing v1
  again (confirmed v1 back to PUBLISHED/live, v2 untouched in history, nothing deleted) — all via
  the real running API, then confirmed the same state rendering correctly in a real browser
  (version list, LIVE/DEPRECATED badges, changelog, template text). Full unit+integration suite
  (388) still green.

### 31. ✅ Tenants had no real directory, Settings had no profile/password — both features already existed in IAM, just not reachable from here
The last of the UI audit's five gaps. Tenants showed a raw-UUID switcher only ("IAM has no
endpoint that lists every tenant"); Settings only had two OAuth toggles, no profile or password
management.
- **The premise was wrong — investigated the real IAM backend (`multi-tannet-auth-services`, a
  separate NestJS/Prisma service) before building anything there**, since the user explicitly
  authorized extending it if actually needed. It wasn't: `GET /tenants` (paginated, gated by a
  real `tenant:read_all` permission already granted to `super_admin`) and `GET`/`PATCH /profile` +
  `POST /auth/password/change` all already exist, fully built and correctly permissioned — this
  app's own `packages/sdk/iam/` just never had a method calling them, and the frontend never had a
  screen for them. **Zero changes to the IAM service were needed.**
- **Fixed, entirely on the frontend**: `frontend/src/app/api/iam/[...path]/route.ts`'s existing
  deliberate allowlist proxy (cookie-authenticated, explicit method+path patterns only — see its
  own docstring) gained four more routes: `GET /tenants`, `GET`/`PATCH /profile`,
  `POST /auth/password/change` (and `PATCH` added to the route's exported HTTP methods, which
  only had GET/POST/DELETE before). `TenantsPage` now shows a real directory table (name, slug,
  status, created date, "Browse as") above the existing by-ID switcher, which stays as a fallback.
  `SettingsPage` gained Profile (name/display name/phone, editable) and Password (change) cards,
  matching its own existing `/api/iam/auth/social/*` call pattern exactly (same tolerant
  `{success,data}`-then-`{data}` double-unwrap, same local `json()` helper).
- **Verified live, through the real running app**: `GET /api/tenants` with a real super_admin
  token returned both real tenants in this environment; loaded the Tenants page in a real browser
  and confirmed the same two rows render correctly. For Settings, actually changed the real
  profile's `displayName` through the UI (not just a mock), confirmed via a direct API call that
  IAM genuinely persisted it, then reverted it through the same UI and confirmed it cleared —
  a real round-trip, not just "the form submits." Password change was verified by code review and
  UI inspection only, not a live submission — deliberately: this account's documented bootstrap
  credentials are shared dev infrastructure this session (and future ones) depends on being able
  to log in with, and changing it for a test would be a real, if reversible, disruption not worth
  the risk for a straightforward passthrough to an endpoint the recon already confirmed works.
  Frontend `tsc --noEmit` and the full Vitest suite (29) both clean throughout.

### 32. ✅ Agents/Model Profiles were create-only, Documents showed raw uploader IDs, Team had no real members list
A second, deeper UI sweep (after item 31) specifically hunting for smaller gaps the first pass
hadn't prioritized found four more real, consistent product gaps — not polish:
- **Agents and Model Profiles had no edit or deactivate** — confirmed at the backend, not just the
  UI: `packages/api/routers/{agents,models}.py` only ever had `POST`/`GET`, no `PATCH`. Both
  `AGENTS_WRITE`/`MODELS_WRITE` permission codes already existed, implying "write" was meant to
  cover more than create. **Fixed**: `PATCH /agents/{id}` and `PATCH /model-profiles/{id}`
  (partial update, re-validates the name-uniqueness and model-profile-exists checks the create
  path already had), plus an Edit dialog and an Activate/Deactivate button on both admin pages.
- **Two real bugs found and fixed in the IAM SDK while building the "Uploaded by" name
  resolution** (`packages/sdk/iam/user.py`, `models.py`) — both genuinely dead code until now,
  confirmed live, not just by inspection:
  1. `User.model_validate()`'s field names didn't match IAM's real response at all — expected a
     required `tenantId` that doesn't exist (a user's tenant memberships are a many-to-many via
     `user_tenant_roles`, not a field on the user — every real call would have failed validation),
     `id` instead of the real `internalId`, `isVerified` instead of `isEmailVerified`.
  2. `get_user()` sent no `Authorization` header at all; IAM correctly rejected every call with
     401 "Access denied. No token provided." Fixed to forward the caller's bearer token, same
     idiom as `get_tenant()`. New `GET /users/{id}` (RAG backend, mirrors `GET /tenants/{id}`
     exactly) and `GET /users` (tenant-scoped list, new `list_users()` SDK method) now back a real
     `useUser()`/`useTenantUsers()` hook pair. Documents' "Uploaded by" row resolves a real name
     instead of a truncated UUID; Team gained a real Members table (name/email/status) above the
     existing invitations list — honestly disclosed limit: IAM's list endpoint doesn't return a
     member's specific role, only membership, so that column isn't there.
- **Verified live**: `GET /api/v1/users/{id}` and `GET /api/v1/users` both confirmed against the
  real running IAM through the RAG backend (5 real users returned for the real tenant, correct
  names/emails); `PATCH /agents/{id}` and `PATCH /model-profiles/{id}` both confirmed — edited a
  real field, confirmed via `GET`, reverted to the original value; both activate/deactivate
  toggles confirmed round-trip (off then on). Full backend suite (391-392, one pre-existing flaky
  integration test confirmed unrelated by re-running it alone — passes in isolation) and frontend
  `tsc --noEmit`/Vitest (29) clean. Browser-level UI screenshots not captured this pass — the
  Chrome extension disconnected after a Docker Desktop restart mid-session; every change here is
  instead verified at the real HTTP layer the UI calls, same backend the rest of this item's
  manual browser testing (item 31) used.

### 33. ✅ No API key support at all — zero way to call this API outside a browser session
A real, genuine enterprise-platform gap, found by auditing against standard SaaS capabilities
rather than a UI sweep: this app had no concept of a programmatic credential anywhere —
everything went through an IAM-issued browser session token. No CI pipeline, integration,
or script could call this API at all without one.
- **Design**: a tenant-scoped `ApiKey` (`packages/domain/models/api_key.py`) — raw value shown
  exactly once at creation (`rag_live_<32 random url-safe chars>`), only its SHA-256 hash ever
  stored, same handling a password gets. `AuthService.resolve()` (`packages/auth/service.py`)
  now branches on the token's shape: `rag_live_` prefix goes to this app's own `api_keys` table
  instead of an IAM round-trip, resolving to a synthetic `CurrentUser` with `roles=["admin"]` and
  every permission code this app defines (`_ALL_PERMISSION_CODES`, collected from `Permission`
  itself so it can't drift out of sync) — matching exactly what the real "admin" role already has
  via `scripts/iam_rbac_seed.sql`, not a privilege escalation. Attributed back to whoever created
  it (`created_by_user_id`/`email`) for audit purposes.
- **A real architectural constraint hit and solved, the same shape as item 29's**: the auth
  middleware runs before any route-level dependency establishes a DB session, so API-key lookup
  needed its own path to the database. Wired `database.session_factory` directly into
  `AuthService` (`packages/infrastructure/container/iam.py`) — a short-lived session opened and
  closed entirely within one `resolve()` call, independent of the request-scoped session every
  route handler shares.
- New routes: `POST/GET /api-keys`, `DELETE /api-keys/{id}` (revoke — not a hard delete, the row
  stays for the audit trail). New frontend "API Keys" page under Administration (both `admin` and
  `tenant_admin` — a tenant-scoped credential, not a platform-wide one) with a one-time reveal
  dialog and a copy button.
- **Verified live, including the two properties that actually matter for something this
  security-sensitive**: created a real key through the real API, then authenticated a real request
  to `GET /agents` using *only* that raw key — no JWT anywhere — and it worked. Confirmed **tenant
  isolation holds**: sent a deliberately spoofed `X-Tenant-ID` header for a different tenant
  alongside the key, and the response still came from the key's own tenant, proving a key can't be
  used to reach another tenant's data by changing a header (`require_uuid_header`'s existing
  `can_override_tenant` check already requires `super_admin`, which API keys deliberately don't
  get). Confirmed revocation is immediate (revoked key → 401 on the next call) and a garbage key is
  rejected cleanly (401, no crash). Then did the same create → reveal → revoke cycle through the
  real browser UI end to end (screenshots confirm the one-time-reveal dialog, the masked list, and
  a real toast on revoke) once the Chrome extension reconnected mid-session.
- New permission codes (`api_keys:read`/`write`) needed mapping on the IAM side the same way item
  11's original taxonomy did — re-ran the updated `scripts/iam_rbac_seed.sql` (now 29 codes × 3
  roles) against the real IAM database.

### 34. ✅ Tenant IDs shown as raw UUIDs in several places — now resolved to real names
User-reported: several admin screens showed a tenant as a raw (sometimes truncated) UUID instead
of its real name, with no obvious reason the ID specifically was needed there.
- **Feature Flags had an actual, unambiguous bug**, not just a polish gap: the Scope column showed
  `flag.tenant_id.slice(0, 8)…` with zero name resolution, for every tenant-scoped override, every
  time. The "New flag" form was worse — a free-text box asking an admin to paste a tenant's raw
  UUID from memory, with no directory to look it up against inside the app at all.
- **Fixed:** Scope column now resolves through the same `useTenant()` id→name lookup Documents'
  "Uploaded by" and the Tenants page already use. The New Flag form's text box became a real `
  <select>` populated from the tenant directory (the same `/api/iam/tenants` fetch the Tenants page
  already does) — "Global default" plus every real tenant by name, nothing typed blind anymore.
- **Three more spots** (`dashboard-view.tsx`, `topbar.tsx`, `workspace-switcher.tsx`) already
  resolved to a real name via `useTenant()` correctly in the common case, but fell back to the raw
  UUID while that lookup was still loading — a brief but real flash of an ID where a name was
  about to appear a moment later. Changed the fallback to a lightweight `…` instead; the "Switch by
  ID" box and "Recently viewed" pills on the Tenants page were left exactly as-is, since that's the
  one place in the app where typing/showing a raw ID is genuinely the point of the feature.
- **Verified live**: created a real tenant-scoped feature flag via the API, loaded the Feature
  Flags page, and confirmed the Scope column shows "EasyDev" (the tenant's real name), not a
  truncated UUID — screenshot confirmed. Opened the New Flag dialog and confirmed its Scope
  dropdown lists real tenant names (`["Global default", "E2E Switch 1790356435", "EasyDev"]`) via a
  direct DOM check. `tsc --noEmit` and the full Vitest suite (29) both clean.
- **User correctly pushed back on the "Switch by ID" carve-out above** — the principle isn't "raw
  IDs are fine for a power-user feature," it's that an ID is a developer concept and a user should
  never need to see or type one unless there's genuinely no name to show instead. Fixed properly:
  the topbar's admin cross-tenant switcher (previously a free-text box with placeholder "Switch to
  a different tenant ID…") is now a `<select>` of real tenant names, same pattern as
  `WorkspaceSwitcher`. The Tenants page's separate "Switch by ID" card is gone entirely — it was
  fully redundant once the Directory table above it already has a name-based "Browse as" button on
  every row — and "Recently viewed" now resolves purely against the already-fetched directory data
  (by name), never rendering a raw id even as a fallback; an entry whose tenant no longer resolves
  is silently dropped rather than shown as an orphaned UUID. The repeated `/api/iam/tenants` fetch
  across three components (Tenants page, Feature Flags, topbar) was pulled into one shared
  `useTenantDirectory()` hook (`frontend/src/hooks/use-tenant-directory.ts`) along the way, rather
  than copy-pasting it a third time.
- **Re-audited the rest of the app for the same `.slice(0, 8)`-style truncated-id pattern** to make
  sure nothing else tenant-related was missed: every remaining instance (Retrieval Log's
  retrieval/request/trace ids, Knowledge Sources' sync-run history, Feedback's message id,
  Documents' sync id) is on an admin-only diagnostic view for something that has no "name" concept
  at all — a sync run or a trace isn't a named entity the way a tenant/user/document is — or already
  tries a real name first and only falls back to an id on genuine lookup failure (Documents'
  "Uploaded by", Observability's/Retrieval Log's document references). None of those are the same
  bug; left as-is.
- **Verified live, again**: used the topbar's new dropdown to actually switch tenants (not just
  render it) — confirmed "Viewing tenant: E2E Switch 1790356435" after selecting it, confirmed
  switching back to "EasyDev" worked too, both via the real running app, console clean throughout.
  `tsc --noEmit` and Vitest (29) clean.
- **Correction to the paragraph above**: "tries a real name first and only falls back to an id on
  genuine lookup failure" was still a raw-id leak, just a rarer one — a user should never see a
  UUID, including on an IAM outage. Documents' `UploadedBy` and Feature Flags' `ScopeBadge` now
  fall back to the words "unknown user" / "unknown tenant" instead of `userId.slice(0, 8)` /
  `tenantId.slice(0, 8)…` when resolution genuinely fails.

### 35. ✅ Audit trail existed but only covered documents/knowledge-sources — agents, model
profiles, feature flags, API keys, tools, and prompts changed with zero record of who did it

`packages/domain/models/audit_event.py` and `AuditService` were already solid — append-only,
best-effort (a logging failure never breaks the operation it's auditing), secrets stripped from
`detail` — and `GET /observability/audit` already existed with pagination and an `action` filter.
But only `documents.py`, `knowledge_sources.py`, and `retrieval_settings.py` ever called
`audit().record(...)`. Every admin action built this session — creating or editing an agent,
minting or revoking an API key, publishing a prompt version (the app's own rollback mechanism),
toggling a feature flag, registering a model profile or a webhook tool — left no trace at all.
For a platform being evaluated for enterprise sale, "who changed this and when" on exactly these
actions is what a security review asks for first.
- **Fixed**: added `audit().record(...)` calls to `agents.py` (create/update), `models.py`
  (create/update — model profiles are global, not tenant-scoped, so these use
  `DEFAULT_TENANT_ID` as the audit scope, same sentinel already used wherever no `X-Tenant-ID`
  header is sent), `feature_flags.py` (create/toggle/delete — a global flag's audit scope is the
  acting admin's own tenant, with the flag's real scope recorded in `detail`), `api_keys.py`
  (create/revoke), `prompts.py` (create prompt/create version/publish version), and `tools.py`
  (create).
- **Audit trail UI gap**: `actor_id` was already in the API response and the TypeScript type, but
  the Observability page's Audit trail table never rendered it — no "Who" column at all. Added
  one, resolving through `useUser()` (same idiom as Documents' "Uploaded by"); a `null` actor_id
  (a system-triggered event like a scheduled re-sync) renders as "system", never a blank or an id.
  Also wired up the `action` filter the backend already supported but the UI never exposed, as a
  plain text input above the table.
- **Re-swept for the same raw-id-fallback issue** found in item 34 above while in this file —
  Documents' `UploadedBy` and Feature Flags' `ScopeBadge` fixed as noted in the correction above.
- **Verified live**: created a new tool definition ("Audit Trail Smoke Test") through the real UI,
  then loaded Observability and confirmed the new `tool.created` row appeared at the top of the
  Audit trail with "Kishor Super Admin" (not a UUID) in the Who column and the right `detail`
  JSON. Typed `tool.created` into the new action filter and confirmed it narrowed the table to
  exactly that one row ("Audit trail (1)"). `tsc --noEmit` and Vitest (29) clean on the frontend;
  backend `pytest` on all five touched routers' API tests is 20 passed / 3 failed, the 3 failures
  being the already-known, already-excluded `"google"` vs `"GOOGLE"` enum-casing bug (identical
  failures existed before this change, confirmed via `gh pr checks` on PR #5 earlier in this
  session) — no regressions.

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
