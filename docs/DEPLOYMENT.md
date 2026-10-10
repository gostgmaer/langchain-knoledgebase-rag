# Deployment

Two ways to run this: bare `uv` + your own Postgres/Redis (fastest for local dev, what `docs/QUICKSTART.md` assumes), or the full Docker Compose stack (closer to how it'd actually run somewhere). This document covers the second. Both the Dockerfile and a couple of real bugs in the compose/Makefile setup were found and fixed while writing this — noted inline, since they're exactly the kind of thing that silently breaks a "just run `make dev`" experience.

---

## 1. The working path: `docker-compose.yml`

The root-level `docker-compose.yml` is the one with real, complete content — five services: `api`, `worker`, `postgres` (pgvector-enabled), `redis`, and `pgadmin` (optional DB GUI).

```bash
cp .env.example .env
# fill in at minimum: GOOGLE_API_KEY (or another provider's key + AI_DEFAULT_PROVIDER),
# POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB (must match the credentials embedded in DATABASE_URL),
# UPLOAD_SERVICE_URL (see step 7 below — document upload genuinely depends on this now)

docker compose up -d --build
```

What happens:
1. `postgres` starts first, using the official `pgvector/pgvector:pg17` image — it self-initializes from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` (these didn't exist in `.env.example` until this pass; without them the official Postgres image refuses to initialize at all).
2. `redis` starts alongside it.
3. `api` and `worker` both wait for `postgres`/`redis` to report **healthy** (not just "started" — `depends_on: condition: service_healthy`) before starting, via the healthchecks each service defines.
4. `api` builds from `docker/Dockerfile` (a two-stage build: `uv sync --locked --no-dev` in a builder stage, then just the resulting `.venv` copied into a slim runtime image, running as a non-root `app` user) and serves on `:8000`.
5. On its own startup (inside the container, same as running locally), the app's `lifespan()` (`packages/api/lifespan.py`) creates the `vector` Postgres extension and runs `Base.metadata.create_all()` — **this is schema-creation, not a real migration system**; see §3.
6. Still at startup, `lifespan()` also sets up a real, Postgres-backed LangGraph checkpointer (`langgraph-checkpoint-postgres`, wrapped via `ThreadedPostgresSaver` — see `docs/ARCHITECTURE_TUTORIAL.md` §13) so conversation state survives a restart. This works correctly both inside the container (Linux) and running `uvicorn packages.api.app:app` bare on native Windows — the startup log should show `Persistent (Postgres-backed) checkpointer ready.` in both. If it instead shows `Could not set up persistent checkpointer, falling back to in-memory`, that means Postgres itself is unreachable — worth investigating like any other connection failure, not a platform difference to shrug off.
7. **Document uploads (`POST /api/v1/documents`) now depend on a real, separate Upload Service being reachable** (`packages/sdk/upload/`, fixed and wired in this pass — see `docs/CHANGELOG.md`) — it's the durable store for uploaded file bytes, deliberately kept off this app's own disk/container filesystem so files don't accumulate there indefinitely. Set `UPLOAD_SERVICE_URL` to wherever that service actually runs; it is **not** one of the five services in this `docker-compose.yml` and isn't started by `docker compose up` here. `UPLOAD_SERVICE_URL` now correctly points at the real, running Upload Service (`https://fms.easydev.in`) — an unreachable or misconfigured one makes `POST /api/v1/documents` fail outright with a `502`, rather than silently falling back to local storage. **Worth knowing about the real service specifically**: it maintains its own file-type allowlist and rejects `text/plain` uploads (`400`) even though this project's own ingestion pipeline otherwise supports plain-text files — that request will fail at the Upload Service step, not silently succeed.

Check it's actually up:
```bash
curl http://localhost:8000/api/v1/health
```

**A real bug fixed while writing this doc:** the Dockerfile's `HEALTHCHECK` was pinging `http://localhost:8000/health` — but the real route is `/api/v1/health` (the whole API is mounted under an `/api/v1` prefix, see `packages/api/routers/__init__.py`). Docker would have reported the container `unhealthy` forever regardless of whether the app was actually fine. Fixed to the correct path.

**A second real bug, also fixed:** the Dockerfile's final `CMD` was written as a JSON array split across multiple lines with no line-continuation — which Dockerfile syntax doesn't support; each line was being parsed as its own (bogus) instruction. Collapsed to a single line: `CMD ["uvicorn", "packages.api.app:app", "--host", "0.0.0.0", "--port", "8000"]`.

**Optional — `pgadmin`:** the compose file's `pgadmin` service needs its own `PGADMIN_DEFAULT_EMAIL`/`PGADMIN_DEFAULT_PASSWORD` in `.env` (not currently in `.env.example` — it's a dev convenience, not a hard dependency of the app itself) if you want the web GUI at `:5050`; the app runs fine without it.

---

## 2. `make dev` / `make prod` — currently non-functional, use the commands above instead

The `Makefile`'s `dev`/`prod` targets pointed at `docker/compose/docker-compose.dev.yml` / `docker/compose/docker-compose.prod.yml` — paths that have never existed; the real files live at the repo root (`docker-compose.dev.yml`, `docker-compose.prod.yml`). **Fixed the path** (`Makefile` now points at the real locations), but that just exposes the deeper problem:

- **`docker-compose.dev.yml` is an empty placeholder file** — zero services defined. `make dev` will now at least *run* without a "file not found" error, but it won't start anything. If you want a dev-specific compose override (hot-reload volume mounts, debug ports, etc.), it needs to actually be written — there's no existing content to build from.
- **`docker-compose.prod.yml` has real, complete content**, but assumes a **pre-built, already-tagged image** (`image: ghcr.io/gostgmaer/ai-platform:${VERSION:-latest}`) rather than building from `docker/Dockerfile` directly — so `make prod` will fail immediately with an image-not-found error unless you first run something like:
  ```bash
  docker build -t ghcr.io/gostgmaer/ai-platform:latest -f docker/Dockerfile .
  ```
  It also had a broken `env_file: ../../.env` path (assuming the compose file lived two directories deeper than it actually does) — fixed to `.env`.

**Until `docker-compose.dev.yml` gets real content, `docker compose up -d --build` against the root `docker-compose.yml` (§1) is the actual working path** — treat the Makefile's `dev`/`prod` targets as aspirational, not verified, until someone builds out the dev override file for real.

---

## 3. What "deployment-ready" still doesn't mean here

This section had drifted stale (see `docs/BUGS.md` for the full, currently-accurate audit) — corrected below rather than left contradicting the current code:

- **Real Alembic migrations exist** and are live-verified (`docs/BUILD_STATUS.md` "next priorities" #23): two idempotent revisions, driven off the live SQLAlchemy models rather than a frozen DDL list, proven end to end against a genuinely empty database. `packages/api/lifespan.py` still boots via `Base.metadata.create_all()` + `apply_schema_upgrades()` by default (`SCHEMA_INIT_AT_STARTUP=true`) rather than `alembic upgrade head` — that's a deliberate choice for local/single-operator dev convenience, not a gap. See §4 below for the real-migration path a production deploy should actually use.
- **Rate limiting, CORS, and doc-gating are all real and registered** — `RateLimitMiddleware` and `CORSMiddleware` are both in `packages/api/middleware/__init__.py`'s `register_middlewares()`, and `/docs`/`/redoc`/`/openapi.json` are gated off entirely when `APP_ENV=production` (`packages/api/app.py`). `SecurityHeadersMiddleware` (CSP/X-Frame-Options/etc.) is also registered.
- **`worker` runs a real `arq` job queue** — `packages/worker/main.py`'s `WorkerSettings` registers real jobs (document ingestion, scratch-file cleanup), sharing the compose stack's Redis. Falls back to in-process ingestion if Redis is unreachable at `api` startup, rather than failing outright.
- **Multi-replica `api` is safe** — this row used to warn against running more than one replica (in-memory rate limiter/locks with no cross-replica coordination); both genuinely-broken-by-design state stores (`RateLimitMiddleware`, the memory summarize-lock) have since moved to Redis-backed, cross-replica-safe implementations (`docs/BUGS.md` item 2), and §7 below now runs two `api` replicas side by side during every deploy on exactly that strength. Per-replica Prometheus metrics (`MetricsStore`) were re-scoped as correct by design, not a bug — standard Prometheus pattern, a real server aggregates across replicas at query time.
- **Both resolved this pass** (tracked in full in `docs/BUGS.md`): CI has now run on real GitHub
  infrastructure and caught two real bugs (items 4, 26), and RBAC permission-code enforcement is on
  in this environment — the role→permission-code mapping now exists on the IAM side and
  `enable_rbac` is `true`, verified live end to end (item 11). A different environment (a fresh IAM
  database, a new deploy) needs the same mapping step run against it; it isn't something a code
  change alone ships.
- **Secrets in `.env`** was the only secrets mechanism for local/dev; a real Docker-secrets-based mechanism now exists for production (`docs/BUGS.md` item 26, §8 below).

None of this blocks running the stack locally for development or testing — it's the gap between "it runs in a container" and "it's actually production-hardened."

## 4. Running as a restricted database role (Row-Level Security)

The dev `.env` connects as a Postgres **superuser** (or an equivalent role with `BYPASSRLS`), which is
the right tradeoff for solo local development (schema auto-provisions itself on every boot via
`Base.metadata.create_all()` + `apply_schema_upgrades()`) but means the row-level-security tenant
policies (`packages/infrastructure/database/upgrades.py`'s `rls_statements()`) are silently bypassed —
superusers ignore every RLS policy unconditionally. In that mode, tenant isolation is enforced **only**
by the per-repository `tenant_id` filters in application code, with no database-level backstop.

A real deploy should connect as the restricted, non-superuser `rag_app` role instead, so RLS is a
genuine second layer of defense, not just a query-layer convention.

**`docker-compose.prod.yml` now does this automatically** via a one-shot `migrate` service that runs
`alembic upgrade head` (as the table owner) and then `scripts/create_app_role.py` (creates/updates the
`rag_app` role, idempotent) *before* `api`/`worker` are allowed to start
(`depends_on: migrate: condition: service_completed_successfully`) — this is no longer a manual step
someone has to remember. It needs two env vars set in that environment's `.env` (see `.env.example`):

```bash
# The table-owner connection the `migrate` service uses for the actual migration/role-creation DDL
# (normally POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB composed into a URL). Falls back to
# DATABASE_URL when unset, which is only correct when DATABASE_URL is itself still a superuser
# connection — set this explicitly once DATABASE_URL below points at rag_app instead.
MIGRATION_DATABASE_URL=postgresql://<owner-user>:<owner-password>@postgres:5432/<database>

# The password `migrate` sets on the rag_app role — generate a real one, don't reuse the owner's.
APP_DB_PASSWORD=<a real generated password>

# The app itself connects as the restricted role — RLS is genuinely enforced.
DATABASE_URL=postgresql://rag_app:<APP_DB_PASSWORD's value>@postgres:5432/<database>

# rag_app can't run schema DDL — alembic (via MIGRATION_DATABASE_URL, as the owner) is the only path
# schema changes go through now, not the auto-provisioning create_all()/ALTER TABLE this flag gates.
SCHEMA_INIT_AT_STARTUP=false
```

Live-verified end to end against a disposable scratch database, inside the real application image (not
just a bare-host Python process): ran the exact `migrate` command sequence
(`alembic upgrade head && PYTHONPATH=. python scripts/create_app_role.py`) in a container from the
project's own built image, confirmed `rag_app` has exactly the privileges normal operation needs
(`SELECT`/`INSERT`/`UPDATE`/`DELETE` on every table, `USAGE`/`SELECT` on sequences, `CREATE` on the
schema for the LangGraph checkpointer's own `CREATE TABLE IF NOT EXISTS`), confirmed a real login as
`rag_app` reports `rolsuper = f`/`rolbypassrls = f`, and re-ran the same command a second time to
confirm it's genuinely idempotent (safe to re-run after new tables are added, exactly like the
underlying `.sql` it's based on). A full `docker compose -f docker-compose.prod.yml up` run (the
`migrate`→`api`/`worker` dependency chain on real GitHub-free infrastructure, not just the command in
isolation) hasn't been observed yet — pending an actual production deploy to confirm the `depends_on`
ordering behaves the same way compose's `config` validation already confirms it's wired to.

If you're pointing the compose stack at an external/managed Postgres instead and want to run this by
hand, `scripts/create_app_role.sql` (the same statements, via `psql`) still works exactly as before —
see its own header for the one-liner.

## 5. Backup and restore

`docs/BUGS.md` item 3: no backup/restore strategy existed at all before this. Postgres holds 100% of
this app's data, including the vector store itself when `VECTOR_STORE_BACKEND=pgvector` (this dev
`.env`'s current setting) — there is no separate store to fall back on.

```bash
# Back up the running `postgres` compose service to storage/backups/<db>_<UTC timestamp>.dump
# (custom pg_dump format: compressed, selectively restorable). Reads POSTGRES_USER/POSTGRES_DB
# from .env.
scripts/backup_db.sh

# Optionally prune dumps older than N days in the same run:
RETENTION_DAYS=14 scripts/backup_db.sh

# Restore a dump. Destructive (--clean --if-exists): drops and replaces every object in the
# target database first. Prompts for the database name as confirmation unless -y/--yes is passed.
scripts/restore_db.sh storage/backups/my_database_name_20260930T120000Z.dump
```

Both scripts run `pg_dump`/`pg_restore` *inside* the `postgres` container via `docker compose exec`,
so they work identically on the host or in CI without needing a local Postgres client install that
matches the server's major version.

Verified live this pass: backed up the real dev database (2.4MB, 39 tables), restored it into a
disposable scratch Postgres container, and confirmed table count and a real row count (`knowledge_sources`)
matched exactly between source and restore.

**Now scheduled automatically in `docker-compose.prod.yml`** via a `backup` sidecar
(`scripts/backup_db_scheduled.sh`) — same image as `postgres` (so its bundled `pg_dump` always
matches the server's major version), connecting directly over the `backend` network rather than a
docker-socket mount (pg_dump is read-only; no reason to grant a backup sidecar that much
privilege). Runs every `BACKUP_INTERVAL_SECONDS` (default 86400 = daily), pruning dumps older than
`BACKUP_RETENTION_DAYS` (default 14) each cycle, into the `backups-data` volume. Verified live:
ran a disposable instance of the sidecar (15s interval) against the real dev database over the
compose network, confirmed a real 2.8MB dump landed on schedule, and confirmed it's genuinely
restorable (`pg_restore --list` — 313 real TOC entries).

**Still a real, open gap**: `backups-data` is a volume on the same host as `postgres-data` — this
does not by itself survive that host's disk failing. Shipping dumps off-host (S3/a remote volume/
an rsync step) is a genuine operational decision for wherever this actually deploys, not something
to guess at from this repo alone.

## 6. Building and deploying the production image

`docs/BUGS.md` item 7: `docker-compose.prod.yml` requires a pre-built, already-tagged
`ghcr.io/gostgmaer/ai-platform:${VERSION}` image (deliberately, not a floating `latest` — see the
compose file's own comment on why), but nothing in the repo built one, so `docker compose -f
docker-compose.prod.yml up` failed immediately with an image-not-found error.

**Since item 52, `.github/workflows/ci.yml`'s `build-and-deploy` job does this automatically** on
every push to `main`/`master` — it builds, tags, and pushes to GitHub Container Registry
(`ghcr.io`, authenticated via the workflow's own `GITHUB_TOKEN`; no registry secret to create or
rotate) whenever backend-relevant paths change. The manual path below is still correct for a local
build or a registry push outside CI; just be aware GHCR packages default to **private** — the
deploy host needs `docker login ghcr.io` with a PAT that has `read:packages`, or the packages need
to be made public, or `docker compose pull` will fail there with an auth error.

```bash
# Build and tag locally:
scripts/build_prod_image.sh 1.4.2

# Build, tag, and push to whatever registry `docker push` is configured for:
PUSH=1 scripts/build_prod_image.sh 1.4.2

# Then deploy:
VERSION=1.4.2 docker compose -f docker-compose.prod.yml up -d
```

Builds from `docker/Dockerfile` once and tags it for both `api` and `worker` — they already share
the exact same dependency set (see `docker/Dockerfile.worker`'s own comment) and
`docker-compose.prod.yml` already references one image for both services. If they ever genuinely
diverge, this script and the compose file's `image:` lines both need to build/reference two tags
instead of one.

**Verified live, end to end, once this environment's earlier build-network issue cleared**: ran
`scripts/build_prod_image.sh 0.1.0-test` for real — `docker build -t easydev/ai-platform:0.1.0-test
-f docker/Dockerfile .` completed cleanly (2.79GB image), confirmed with `docker images`, then
removed the test tag again (it was only ever for verification, not a real release).

## 7. Zero-downtime deploys

`docs/BUGS.md` item 9. A previous pass left this deliberately undone, documenting three real
options rather than picking one unasked (reverse proxy + two versions side by side; move to an
orchestrator like Swarm/Kubernetes; or accept brief downtime per deploy as a legitimate choice).
This pass built the first option for real.

**How it works.** `docker-compose.prod.yml` now has three services where there used to be one
`api`: `traefik` (the only public entrypoint, `:8000`), and `api_blue`/`api_green` — two identical
replicas of the same logical Traefik service (same `traefik.http.services.api...` labels on both),
neither publishing a host port directly. Traefik discovers backends via Docker and automatically
load-balances across every *running* container advertising that service name — and automatically
skips any container whose Docker `HEALTHCHECK` isn't reporting healthy (already baked into
`docker/Dockerfile`, no extra Traefik config needed for that part).

Deploy with the script, not a raw `docker compose up -d`:

```bash
VERSION=1.4.3 scripts/deploy_blue_green.sh
```

It starts whichever color isn't currently running on the new version, waits for its own
`HEALTHCHECK` to report healthy (Traefik is routing to *both* the old and new containers during
this window — the actual mechanism that avoids a gap), then stops and removes the old color. If
the new color never goes healthy within `HEALTH_TIMEOUT_SECONDS` (default 120s), it's torn down
instead and the old color is left running, untouched — a real rollback on failure, not just a
deploy that might leave things broken. First-ever deploy (neither color running yet) starts
`api_blue`, same as any other deploy, with no old color to drain afterward.

**Not changed**: `worker` stays single-instance with `restart: always`, same as before. It doesn't
serve HTTP traffic that needs a gap-free cutover the way `api` does — arq job state lives in
Redis, so a brief worker restart just delays in-flight jobs rather than dropping a live request;
a different risk profile, out of scope for this specific gap.

**Verified**: `docker compose -f docker-compose.prod.yml config` resolves cleanly — `api_blue`/
`api_green` correctly carry no direct port publish, identical Traefik labels on both, and
`traefik`'s own command/port/socket-mount config all render as intended. `scripts/
deploy_blue_green.sh` passes `sh -n` (syntax-only check). Full live verification (an actual
`VERSION=x` → `VERSION=y` deploy, watching requests succeed throughout) deferred — this
environment's Docker Desktop was down for this pass.

## 8. Production secrets (Docker secrets)

`docs/BUGS.md` item 26 — §3 above used to flag `.env` as the only secrets mechanism for genuinely
sensitive values (API keys, passwords, connection strings). `docker-compose.prod.yml` now has a real
alternative for production: Docker Compose's file-based `secrets:` mechanism, which works with a plain
`docker compose up` (no Swarm needed).

Two secrets exist, not one per key. `secrets/app.env` is an ordinary `KEY=value` file (same shape as
`.env`) holding every secret-managed value except the Postgres superuser password, mounted as a
single Docker secret at `/run/secrets/app_env`. Every app-process service (`migrate`, `api_blue`,
`api_green`, `worker`, `backup`) runs `scripts/docker_secrets_entrypoint.sh` as its `entrypoint:`,
which sources that file directly (`set -a; . /run/secrets/app_env; set +a`) before exec'ing the
service's real command. The application code itself needed zero changes — `packages/config/*.py`
(pydantic-settings) already just reads plain environment variables, exactly as it does today from
`.env`. `postgres_password` is kept as its own, separate single-value secret: the official Postgres
image natively supports a `POSTGRES_PASSWORD_FILE` convention, which expects a file containing only
the raw value, not `KEY=value` lines — `postgres` mounts it directly with no wrapper script involved,
and `backup` reads the same password back out of `app.env`'s own `POSTGRES_PASSWORD=` line (via the
wrapper) since its image has no native `_FILE` support.

One file for everything else, not twenty, is a deliberate choice: Compose's `secrets:` mechanism only
requires each secret be *a* file — nothing requires a 1:1 split per key, and the per-service wiring
(`entrypoint:` + `secrets: *app-secrets`) is identical either way. A single `KEY=value` file is less
setup friction (one file to fill in, not twenty) and the entrypoint script no longer needs a
filename-to-env-var-name convention, just a plain `source`.

`app.env` covers database/cache credentials (`DATABASE_URL`, `MIGRATION_DATABASE_URL`,
`POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, `REDIS_URL`), auth/crypto secrets (`JWT_SECRET`,
`IAM_CLIENT_SECRET`, `IAM_INTROSPECTION_API_KEY`, `FILE_UPLOAD_HMAC_SECRET`,
`CONNECTOR_CREDENTIAL_KEYS`, `CONNECTOR_RENDER_TOKEN`), LLM-provider keys (`GOOGLE_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`), and tool/integration keys (`SERPER_API_KEY`,
`TAVILY_API_KEY`, `OPENWEATHER_API_KEY`, `NEWSAPI_API_KEY`, `UPLOAD_SERVICE_API_KEY`,
`LANGCHAIN_API_KEY`). Plain endpoints/URLs with no embedded credential and ordinary non-sensitive
config (timeouts, feature flags, model names) deliberately stay in `.env` via `env_file`, same as
always — see `secrets/README.md` and `secrets/app.env.example` for the full, current breakdown and
setup steps (copy `app.env.example`/`postgres_password.txt.example` to their real, gitignored
counterparts). Production's real `.env` should omit every key in `app.env.example` entirely — if both
`.env` and `app.env` set the same variable, `app.env` wins (the entrypoint's `export` runs after
`env_file` is already loaded), but leaving it out of `.env` for real avoids two sources of truth for
one value.

**Verified in two passes.** The original per-key-file design was verified live inside the real
application image (`langchain-knoledgebase-rag-api:latest`): mounted a disposable set of fake secret
files, ran the container against a disposable scratch Postgres with a deliberately-wrong
`-e DATABASE_URL=...`/`-e MIGRATION_DATABASE_URL=...` override, and confirmed the secret-file value
won; `alembic upgrade head` and `scripts/create_app_role.py` both then succeeded against it.

Consolidating to a single `app.env` file changed how that file is loaded — from reading each
raw-value file with `cat` to parsing one `KEY=value` file — which is a real behavior change worth
re-verifying on its own: **sourcing** a `KEY=value` file with `.`/`source` (the first version of this
change) was tried and found to be a genuine bug, not just a style choice — it runs each line as a
shell assignment, so a value containing `$` is misparsed (confirmed: `p@ss$w0rd` failed with
`w0rd: unbound variable`) and a value containing backticks or `$(...)` would execute arbitrary
commands. Fixed by parsing the file line-by-line with `read` instead (inert text, no shell
expansion) — confirmed via standalone shell tests that `$`, `` ` ``, and `$(...)` inside a value all
now come through completely literally. A fresh full-container re-run of the live Postgres test above
against this exact parsing logic hasn't been repeated this pass (Docker Desktop was down in this
environment) — the standalone shell-level verification covers the part that actually changed.
`docker compose -f docker-compose.prod.yml config` resolves cleanly with the consolidated two-secret
block and no real `app.env`/`postgres_password.txt` present (Compose only needs them to exist at `up`
time, not at `config` time).

## 9. Enabling fine-grained RBAC

`docs/BUGS.md` item 11 — `require_permission()`'s permission-code checks (`packages/api/
permissions.py`) are gated behind the dynamic `enable_rbac` feature flag, default off. Turning it on
for real needs two separate steps, in order:

1. **Map permission codes to roles on the IAM side**: `scripts/iam_rbac_seed.sql` grants every code
   in `packages/api/permissions.py` to IAM's `super_admin`/`admin`/`tenant_admin` roles — exactly the
   roles `RAGSettings.admin_roles` already lets through `require_admin()` unconditionally, so this
   reproduces current access, not a narrower one. Run it against IAM's own database:
   `psql -U postgres -d easydev -f scripts/iam_rbac_seed.sql` (or via `docker exec -i core-postgres
   psql ...` for a Dockerized IAM instance). Idempotent — safe to re-run after a new code is added to
   `permissions.py`.
2. **Flip the flag**: `scripts/set_feature_flag.py enable_rbac true` (global) or with `--tenant-id` to
   scope it to one tenant, via the admin Feature Flags page, or `PATCH /api/v1/feature-flags/{id}`.
   Deliberately a separate step from (1) — flipping it before the mapping exists locks every admin
   out instead of narrowing anything.

**Verified live, end to end, through the real auth layer**: ran both scripts against this dev
environment's real IAM/RAG databases, logged in as the bootstrap super admin via the real gateway,
confirmed `GET /auth/me` returns the new RAG codes alongside the platform's other permissions,
confirmed `GET /api/v1/feature-flags` shows the running API's own live view of `enable_rbac` as
`true`, and confirmed `GET /api/v1/agents`/`GET /api/v1/knowledge-sources` still return `200` with a
real admin token — RBAC is genuinely enforcing, not a no-op, and no admin was locked out.
