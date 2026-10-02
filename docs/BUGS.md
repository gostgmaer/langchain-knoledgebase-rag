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

### 11. ✅ Fine-grained, permission-code RBAC is dead code — taxonomy now proposed and wired, inert until deliberately turned on
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
- **Still open, by design, not glossed over**: nobody's real IAM-issued JWT carries any of these
  codes yet — turning `ENABLE_RBAC` on anywhere real, before a role→code mapping exists on the IAM
  side, would lock every admin out of these routes rather than narrow anything. This taxonomy is a
  proposal ready for review, not a decision to flip the flag on.

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
