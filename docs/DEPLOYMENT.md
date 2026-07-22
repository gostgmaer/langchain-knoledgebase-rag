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

Worth being explicit about, since none of this is fixed by the changes in this pass:

- **No real database migrations.** `alembic/` exists (`alembic.ini`, one versions file: `44b52e61b180_initial_schema.py`), but the app doesn't actually run migrations on startup — `packages/api/lifespan.py` calls `Base.metadata.create_all()` directly against the live models every time the app boots, which only ever *adds* missing tables, never alters existing ones. Schema drift (a column added to a model after the table already exists in a running database) has to be applied by hand — this has happened for real in this project's history (`model_profiles.vector`, `memories` table dimension change), each time via a manual `ALTER TABLE`. `make migrate`/`make revision` exist as Makefile targets but aren't part of any deploy flow.
- **`worker` doesn't do anything yet.** `packages/worker/main.py` is a heartbeat loop (`logger.info("Worker heartbeat...")` every 30s) — real background job infrastructure (`arq`, listed as a dependency) is installed but never wired up. Document ingestion already runs off the request path via FastAPI `BackgroundTasks` instead (see `docs/ARCHITECTURE_TUTORIAL.md` §5), which is why this hasn't blocked anything yet — but the `worker` container in the compose stack is not currently load-bearing.
- **No rate limiting, no CORS configuration, docs exposed unconditionally.** `packages/api/middleware/rate_limit.py` exists but isn't registered (`docs/ARCHITECTURE_TUTORIAL.md` §4.1's middleware list is the real, live set — rate limiting isn't in it). `/docs`/`/redoc`/`/openapi.json` are always mounted, in every environment, with no env-gating.
- **Secrets in `.env`** are the only secrets mechanism — no Docker secrets, no external secrets manager integration. Fine for local/dev, worth revisiting before anything resembling a real production deploy.

None of this blocks running the stack locally for development or testing — it's the gap between "it runs in a container" and "it's actually production-hardened."
