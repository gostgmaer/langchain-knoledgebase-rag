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
- **`docker-compose.prod.yml` has real, complete content**, but assumes a **pre-built, already-tagged image** (`image: easydev/ai-platform:${VERSION:-latest}`) rather than building from `docker/Dockerfile` directly — so `make prod` will fail immediately with an image-not-found error unless you first run something like:
  ```bash
  docker build -t easydev/ai-platform:latest -f docker/Dockerfile .
  ```
  It also had a broken `env_file: ../../.env` path (assuming the compose file lived two directories deeper than it actually does) — fixed to `.env`.

**Until `docker-compose.dev.yml` gets real content, `docker compose up -d --build` against the root `docker-compose.yml` (§1) is the actual working path** — treat the Makefile's `dev`/`prod` targets as aspirational, not verified, until someone builds out the dev override file for real.

---

## 3. What "deployment-ready" still doesn't mean here

This section had drifted stale (see `docs/BUGS.md` for the full, currently-accurate audit) — corrected below rather than left contradicting the current code:

- **Real Alembic migrations exist** and are live-verified (`docs/BUILD_STATUS.md` "next priorities" #23): two idempotent revisions, driven off the live SQLAlchemy models rather than a frozen DDL list, proven end to end against a genuinely empty database. `packages/api/lifespan.py` still boots via `Base.metadata.create_all()` + `apply_schema_upgrades()` by default (`SCHEMA_INIT_AT_STARTUP=true`) rather than `alembic upgrade head` — that's a deliberate choice for local/single-operator dev convenience, not a gap. See §4 below for the real-migration path a production deploy should actually use.
- **Rate limiting, CORS, and doc-gating are all real and registered** — `RateLimitMiddleware` and `CORSMiddleware` are both in `packages/api/middleware/__init__.py`'s `register_middlewares()`, and `/docs`/`/redoc`/`/openapi.json` are gated off entirely when `APP_ENV=production` (`packages/api/app.py`). `SecurityHeadersMiddleware` (CSP/X-Frame-Options/etc.) is also registered.
- **`worker` runs a real `arq` job queue** — `packages/worker/main.py`'s `WorkerSettings` registers real jobs (document ingestion, scratch-file cleanup), sharing the compose stack's Redis. Falls back to in-process ingestion if Redis is unreachable at `api` startup, rather than failing outright.
- **Genuinely still open** (tracked in full in `docs/BUGS.md`): no CI pipeline, zero frontend test coverage, no load-testing tooling, no backup/restore strategy, and the app is architecturally single-replica-only today (in-memory rate limiter/metrics/locks with no cross-replica coordination) — don't run more than one `api` replica until that's addressed.
- **Secrets in `.env`** are the only secrets mechanism — no Docker secrets, no external secrets manager integration. Fine for local/dev, worth revisiting before a real production deploy.

None of this blocks running the stack locally for development or testing — it's the gap between "it runs in a container" and "it's actually production-hardened."

## 4. Running as a restricted database role (Row-Level Security)

The dev `.env` connects as a Postgres **superuser** (or an equivalent role with `BYPASSRLS`), which is
the right tradeoff for solo local development (schema auto-provisions itself on every boot via
`Base.metadata.create_all()` + `apply_schema_upgrades()`) but means the row-level-security tenant
policies (`packages/infrastructure/database/upgrades.py`'s `rls_statements()`) are silently bypassed —
superusers ignore every RLS policy unconditionally. In that mode, tenant isolation is enforced **only**
by the per-repository `tenant_id` filters in application code, with no database-level backstop.

A real deploy should connect as the restricted, non-superuser `rag_app` role instead, so RLS is a
genuine second layer of defense, not just a query-layer convention. This was live-verified this pass
against a disposable scratch database (real Alembic migration as the owner, `scripts/create_app_role.sql`
applied, then a real API instance booted as `rag_app`): the role has exactly the privileges normal
operation needs (`SELECT`/`INSERT`/`UPDATE`/`DELETE` on every table, `USAGE`/`SELECT` on sequences,
`CREATE` on the schema for the LangGraph checkpointer's own `CREATE TABLE IF NOT EXISTS`), the app boots
cleanly with no RLS-bypass warning, and — the actual point — a raw-SQL check confirmed RLS genuinely
filters rows by `app.tenant_id` when connected as `rag_app`, which it does **not** do as a superuser.

Setup, once per environment:

```bash
# 1. Run the real migration as the table owner (a superuser or the role that will own the tables).
DATABASE_URL=<owner-url> alembic upgrade head

# 2. Create the restricted role (idempotent — safe to re-run after new tables are added).
psql -U <owner> -d <database> -v app_password='<a real generated password>' -f scripts/create_app_role.sql
```

Then, in that environment's `.env`:

```bash
# The app connects as the restricted role — RLS is genuinely enforced.
DATABASE_URL=postgresql://rag_app:<password>@<host>:5432/<database>

# The app no longer tries to create_all()/ALTER TABLE at boot (rag_app doesn't own the tables and
# can't run DDL beyond the one CREATE it's explicitly granted for the checkpointer's own setup) —
# schema changes go through `alembic upgrade head` as the owner instead, as a separate deploy step.
SCHEMA_INIT_AT_STARTUP=false
```

**Not done automatically by any compose file** — `docker-compose.prod.yml` doesn't currently run the
migration/role-creation step or default to this `DATABASE_URL`/`SCHEMA_INIT_AT_STARTUP` pair, since
doing so unconditionally would break the common "point compose at a fresh, unmigrated database" case.
Wire it into whatever deploy automation runs before `docker compose -f docker-compose.prod.yml up`.
