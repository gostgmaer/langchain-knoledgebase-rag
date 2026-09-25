# Local setup runbook - everything needed to run and test the RAG platform

Step-by-step: prerequisites, what to install, which services to start (and in which order), the recommended settings, and how to check each step worked. See [`SERVICE_DEPENDENCIES.md`](SERVICE_DEPENDENCIES.md) for what each service needs and what needs it. Companion to [`ENVIRONMENT.md`](ENVIRONMENT.md), which explains every variable.

Legend: **[verified]** = run successfully on this machine during development. **[check]** = derived from the compose files/code but not re-run from a clean machine; if it fails, the "If it fails" note says where to look.

---

## 0. What you are starting

Only the services this RAG project actually depends on. The payment, lead, job-agent, support-ai and communication services are **not** needed.

| # | Service | Repo | Host port | Why the RAG project needs it |
|---|---|---|---|---|
| 1 | Core Postgres + PgBouncer + Redis | `easydev-infra` (core stack) | 5432, 6379 | IAM's database and cache |
| 2 | **IAM auth-service** (+ `auth-worker`) | `Backend/multi-tannet-auth-services` | 3304 | Users, tenants, roles, invitations, social login, tokens |
| 3 | **API gateway** (+ `gateway-worker`) | `Backend/web-agency-backend-api` | 3301 | Browser/API entry point to IAM (`/api/auth/*`, `/api/iam/*`) |
| 3a | **MongoDB** (external, not started by any compose file) | your own instance or Atlas | 27017 | notification-service and file-upload-service store their data here (`MONGODB_URI` / `MONGO_URI`) |
| 4 | Utility Redis | `easydev-infra` (utility stack) | 6383 | Queue for notifications |
| 5 | **notification-service** (+ `notification-worker`) | `Backend/notification-service` | 4004 | Sends invitation / verification emails for IAM |
| 6 | **Mailpit** | container `axllent/mailpit` | SMTP 1025, UI 8025 | Catches all local email (nothing is delivered for real) |
| 7 | **file-upload-service** | `Backend/file-upload-service` | 4005 | Stores documents uploaded to RAG |
| 8 | RAG Postgres (pgvector) + Redis | this repo (`docker-compose.yml`) | 5442, 6389 | RAG data, embeddings, job queue |
| 9 | **RAG API** + **RAG worker** | this repo | 8088 | The product itself |
| 10 | Jaeger (optional) | this repo | 16686 | Trace viewer |
| 11 | **Frontend** | `frontend/` | 3000 | The web UI |

Dependency order (MongoDB first): **3a -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 11.** IAM needs notification and file-upload URLs to boot, but they only need to *exist* by name on the Docker network - starting them right after is fine as long as you start all of them before testing.

---

## 1. One-time prerequisites

### 1.1 Machine

| Requirement | Recommended | Notes |
|---|---|---|
| OS | Windows 11 + Docker Desktop (WSL2 backend) | Commands below use **Git Bash**. |
| Memory for Docker | **16 GB or more** (this machine: `.wslconfig` `memory=24GB`) | Image builds (the RAG image with PyTorch, IAM/NestJS) were OOM-killed on a low-memory host. Build **one image at a time**; do not run heavy builds in parallel. |
| Disk | 30 GB free | Images ~10 GB, RAG model cache volume ~1 GB. |
| Docker Desktop | Running **before** any command below | If you see `failed to connect to the docker API ... dockerDesktopLinuxEngine`, Docker Desktop is not running: start it and wait for "Engine running". |
| Git Bash | Installed | Do **not** use WSL's `bash`; path handling differs. |
| Node.js | 20+ (this machine: 24) | Only for the frontend (`npm`). |
| MongoDB | Reachable instance (section 1.2b) | Needed by notification and file-upload. |
| Internet | Required on first start | Pulls base images, npm packages, and downloads the reranker model from huggingface.co. |

### 1.2 Repositories (expected locations)

```
C:\Users\kisho\WorkSpace\
  docker network\easydev-infra                 <- compose stacks + env files
  Backend\multi-tannet-auth-services           <- IAM
  Backend\web-agency-backend-api               <- gateway
  Backend\notification-service
  Backend\file-upload-service
  learning\ai\langchain-knoledgebase-rag       <- this repo
```

The infra compose files build images from these sibling folders using relative paths, so keep the layout.

### 1.2b MongoDB (required, not provided by the stacks)

notification-service and file-upload-service will not start without a reachable MongoDB, and no compose file starts one. Use whichever you already have (a local install, Atlas, or the platform's shared instance) and put its URI in `.env.app` (`MONGODB_URI`) and `.env.file-upload` (`MONGO_URI`). If you have none, a throwaway local one **[check]**:

```bash
docker run -d --name mongo --restart unless-stopped -p 27017:27017 -v mongo-data:/data/db mongo:7
# URI for the containers:  mongodb://host.docker.internal:27017/easydev
```

### 1.3 Docker networks (create once)

The stacks share **external** networks. `deploy-local.sh` creates them; if you start stacks by hand, create them first:

```bash
for n in core-network product-network ai-platform-network utility-network; do
  docker network inspect $n >/dev/null 2>&1 || docker network create $n
done
```

### 1.4 Environment files (create once from the examples)

| Stack | Copy | To | Then |
|---|---|---|---|
| Core | `stacks/core/env/.env.*.example` | `stacks/core/env/.env.*` | Fill the values marked `CHANGE_ME` (see 1.5) |
| Utility | `stacks/utility/env/.env.*.example` | `stacks/utility/env/.env.*` | Same |
| RAG | `.env.example` | `.env` | Fill LLM key, IAM and upload values (see 1.6) |
| Frontend | `frontend/.env.local.example` | `frontend/.env.local` | Three URLs (see 1.7) |

All real env files are gitignored. Never commit them.

### 1.5 Recommended settings - infra stacks (local)

Values that must be consistent across files are the ones that break things when they are not. Full table: `ENVIRONMENT.md` section 2.

**Core - `stacks/core/env/.env.auth`** (IAM)
- `FRONTEND_URL=http://localhost:3000`
- `AUTH_PUBLIC_BASE_URL` and `APP_URL`: a valid URL (local: `http://localhost:3304`)
- `CORS_ORIGINS=http://localhost:3000,http://localhost:3301` - **must include the gateway origin** or social login fails with "Untrusted base URL override"
- `BACKUP_CODE_ENCRYPTION_KEY` = 64 hex characters (`openssl rand -hex 32`) - **required**; without it social login and 2FA fail
- `COOKIE_SECRET`, `SSO_SECRET`, `JWT_REFRESH_SECRET` (32+), `JWT_MAGIC_LINK_SECRET`: random values
- `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY`: an RS256 pair (base64 PEM), or the `*_PATH` variants
- `BOOTSTRAP_SUPER_ADMIN_EMAIL` / `_PASSWORD`: the platform admin you will log in with
- `BOOTSTRAP_SERVICE_ACCOUNT_EMAIL` / `_PASSWORD`: must equal `IAM_ADMIN_EMAIL` / `IAM_ADMIN_PASSWORD` in `.env.gateway`
- `IAM_INTROSPECTION_API_KEY`: any random value; reuse it in the RAG `.env`

**Core - `stacks/core/env/.env.gateway`**
- `FRONTEND_URL=http://localhost:3000`, `CORS_ORIGINS` includes `http://localhost:3000`
- `AUTH_SERVICE_URL=http://auth-service:3000`
- `IAM_ADMIN_EMAIL` / `IAM_ADMIN_PASSWORD` as above
- Product keys (payment, job-agent, communication, support-ai, AI workflow): leave the placeholders; the RAG project does not use them.

**Core - shared files**: `.env.shared`, `.env.postgres`, `.env.redis`, `.env.pgbouncer` - the DB and Redis passwords here must equal the ones inside each service's `DATABASE_URL` / `REDIS_URL`.

**Utility - `stacks/utility/env/.env.app`** (notification-service)
- `API_KEY` = the value IAM sends as `NOTIFICATION_SERVICE_API_KEY`
- `EMAIL_HOST=mailpit`, `EMAIL_PORT=1025`, `EMAIL_SECURE=false`, no `EMAIL_USER` / `EMAIL_PASS`
- `EMAIL_FROM=noreply@easydev.in` (any address is fine for Mailpit)
- `MONGODB_URI`: a reachable MongoDB (see 1.2b)

**Utility - `stacks/utility/env/.env.file-upload`**
- `STORAGE_TYPE=local`, `LOCAL_SIGNED_URL_SECRET` = 32+ random chars
- `GATEWAY_INTERNAL_SECRET` = 32+ random chars, and `FILE_UPLOAD_HMAC_SECRET` = the same value
- `MONGO_URI`: a reachable MongoDB (see 1.2b; the service will not start without one)
- `ALLOWED_MIME_TYPES` / `ALLOWED_FILE_EXTENSIONS` must include the document types you will ingest (pdf, docx, txt, md, csv)

### 1.6 Recommended settings - RAG (`.env`)

```dotenv
# --- required to boot (no code default) ---
DATABASE_URL=postgresql://<user>:<pass>@postgres:5432/<db>
POSTGRES_USER=<user>            # must match DATABASE_URL
POSTGRES_PASSWORD=<pass>
POSTGRES_DB=<db>
REDIS_URL=redis://redis:6379/0
JWT_SECRET=<32+ random chars>   # legacy, but must be set
OPENWEATHER_API_KEY=placeholder # required by config even if the weather tool is unused
NEWSAPI_API_KEY=placeholder     # same

# --- auth (IAM) ---
AUTH_REQUIRED=true              # recommended everywhere; false = anonymous default tenant
IAM_BASE_URL=http://host.docker.internal:3301   # the GATEWAY, not the auth-service
IAM_CLIENT_ID=<placeholder>
IAM_CLIENT_SECRET=<placeholder>
IAM_INTROSPECTION_API_KEY=<same as IAM>

# --- upload service ---
UPLOAD_SERVICE_URL=http://host.docker.internal:4005
FILE_UPLOAD_HMAC_SECRET=<same as the upload service's GATEWAY_INTERNAL_SECRET>   # required, else uploads fail
UPLOAD_SERVICE_ROLE=admin

# --- vector store, LLM, embeddings ---
VECTOR_STORE_BACKEND=pgvector
LLM_PROVIDER=google             # google | openai | anthropic | groq
LLM_MODEL=<model id>
GOOGLE_API_KEY=<key>            # or the key for your chosen provider
EMBEDDING_PROVIDER=google
EMBEDDING_MODEL=<embedding model id>
EMBEDDING_DIMENSIONS=1536

# --- recommended for local ---
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
LANGCHAIN_TRACING_V2=false      # unless you have a real LangSmith key
LOG_JSON=true
```

### 1.7 Recommended settings - frontend (`frontend/.env.local`)

```dotenv
RAG_API_URL=http://127.0.0.1:8088/api/v1      # the /api/rag proxy forwards here
AUTH_GATEWAY_URL=http://localhost:3301        # server-to-server gateway address
# AUTH_GATEWAY_PUBLIC_URL=http://localhost:3301   # only if AUTH_GATEWAY_URL is an internal hostname
```

Restart `npm run dev` after any change to this file.

---

## 2. Start everything (in order)

Run from Git Bash. Each step ends with a check; do not continue until it passes.

### Step 1 - Core stack: database, cache, IAM, gateway

```bash
cd "/c/Users/kisho/WorkSpace/docker network/easydev-infra/stacks/core"
docker compose -p easydev-core -f docker-compose.local.build.yml up -d --build \
  core-postgres core-pgbouncer core-redis auth-service auth-worker gateway gateway-worker
```
**[verified]** (the first build is slow; build one service at a time if memory is tight, e.g. `up -d --build auth-service`, then the next.)

Check:
```bash
docker ps --format '{{.Names}}  {{.Status}}' | grep -E "core-|auth-|gateway"
curl -s -o /dev/null -w "gateway login -> %{http_code}\n" -X POST http://localhost:3301/api/auth/login \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:3000' \
  -d '{"email":"<BOOTSTRAP_SUPER_ADMIN_EMAIL>","password":"<BOOTSTRAP_SUPER_ADMIN_PASSWORD>"}'
```
Expect `core-*` healthy and login `200`.
*If it fails:* `docker logs auth-service --tail 50` - a Joi validation message names the missing variable (see `ENVIRONMENT.md` section 5).

### Step 2 - Utility stack: notification and file upload

```bash
cd "/c/Users/kisho/WorkSpace/docker network/easydev-infra/stacks/utility"
docker compose -p easydev-utility -f docker-compose.local.build.yml up -d --build
```
**[verified]** for the services; project name `easydev-utility` follows `scripts/deploy-local.sh` **[check]**.

### Step 3 - Mailpit (local mail catcher)

```bash
docker run -d --name mailpit --restart unless-stopped --network utility-network \
  -p 1025:1025 -p 8025:8025 axllent/mailpit
```
**[check]** - Mailpit is not part of any compose file. The notification service reaches it by the name `mailpit`, so it must share `utility-network`. Open http://localhost:8025 to read emails.
*If invitation emails never arrive:* `docker logs notification-worker --tail 50`, and confirm `EMAIL_HOST=mailpit` in `.env.app`.

Check steps 2-3:
```bash
docker ps --format '{{.Names}}  {{.Status}}' | grep -E "notification|file-upload|utility-redis|mailpit"
curl -s -o /dev/null -w "upload health -> %{http_code}\n" http://localhost:4005/health/live
curl -s -o /dev/null -w "notification health -> %{http_code}\n" http://localhost:4004/v1/health/live
```

### Step 4 - RAG database, cache, API and worker

```bash
cd "/c/Users/kisho/WorkSpace/learning/ai/langchain-knoledgebase-rag"
docker compose --profile full up -d --build
```
**[verified]** in the form `docker compose up -d --build api worker` (plus postgres/redis starting as dependencies). The `full` profile also starts Jaeger. The first API start is slow (the reranker model loads); wait for healthy:

```bash
until [ "$(curl -s -o /dev/null -w '%{http_code}' localhost:8088/api/v1/health)" = 200 ]; do sleep 5; done; echo "RAG API is up"
```

### Step 5 - Database migrations (first time and after schema changes)

```bash
docker compose exec api alembic upgrade head
```
**[check]** - migrations are **not** run automatically at container start. `alembic` is a dependency of the project and `Makefile` has `migrate: uv run alembic upgrade head`, but that form reads the container hostname `postgres` from `.env`, so run it inside the container as shown.
*If tables are missing* (errors like `relation "..." does not exist`), this step was skipped.

### Step 6 - Reranker model (first time only)

The first chat query downloads a ~90 MB model from huggingface.co. On flaky networks the download can fail with TLS errors. The cache lives in the Docker volume `hf-cache`, so it only has to succeed once. Pre-fetch it with retries:

```bash
docker compose exec api sh -c 'for i in 1 2 3 4 5 6; do python -c "from huggingface_hub import snapshot_download; snapshot_download(\"cross-encoder/ms-marco-MiniLM-L6-v2\")" && break; sleep 3; done'
```
**[verified]**. Alternative: set `ENABLE_RERANKING=false` to skip the model entirely.

### Step 7 - Frontend

```bash
cd frontend
npm install        # first time only
npm run dev        # http://localhost:3000
```
**[verified]**.

---

## 3. Verify the whole stack (smoke test)

| # | Check | Command / action | Expect |
|---|---|---|---|
| 1 | IAM login | Step 1 `curl` | 200 |
| 2 | RAG health | `curl localhost:8088/api/v1/health` | 200 |
| 3 | RAG rejects anonymous | `curl -i localhost:8088/api/v1/knowledge-bases` | **401** (with `AUTH_REQUIRED=true`) |
| 4 | UI login | http://localhost:3000, sign in as the bootstrap admin | Lands on the admin dashboard |
| 5 | Via proxy | Browser: any RAG page loads data (agents, knowledge bases) | No 401s in the network tab |
| 6 | Invite | Team page -> invite an email | Email appears in http://localhost:8025 |
| 7 | Accept invite | Open the link from the email | Signed out, then sign in again works |
| 8 | Upload | Documents -> upload a `.txt` | 202, the job goes `QUEUED` -> `SUCCEEDED` |
| 9 | Chat | Ask a question about the uploaded document | Answer with citations (needs a working LLM key) |
| 10 | Social login | Login page shows a provider button only when that provider is enabled in IAM | Buttons hidden until configured |

`scripts/verify-stack.sh` in `easydev-infra` (read-only) checks container health and DB state for the core stack.

### Enabling social login locally (optional)

1. Create an OAuth app at Google / Microsoft / Facebook and register the redirect URI `http://localhost:3301/api/auth/social/<google|microsoft|facebook>/callback`.
2. Put the credentials in `.env.auth` (`GOOGLE_CLIENT_ID` ...) and recreate `auth-service`.
3. As super admin, set `auth.social.enabled=true` **and** `auth.social.<provider>=true` (IAM platform settings, `PUT /api/iam/settings/<key>`).
4. Reload the login page: the button appears. For Microsoft account linking by email set `MICROSOFT_TENANT_ID` to a specific tenant or `consumers` (not `common`).

---

## 4. Everyday commands

```bash
# status of everything
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# logs
docker logs -f langchain-knoledgebase-rag-api-1
docker logs -f langchain-knoledgebase-rag-worker-1      # worker logs only
docker logs -f auth-service
docker logs -f notification-worker

# after changing a .env file, recreate (a plain restart may not re-read env_file)
docker compose up -d api worker                          # RAG
docker compose -p easydev-core -f docker-compose.local.build.yml up -d auth-service   # from stacks/core

# rebuild one service after code changes
docker compose up -d --build api worker                  # RAG

# stop (keeps data)
docker compose --profile full stop

# wipe RAG data (database + queue + model cache) - destructive
docker compose --profile full down -v
```

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `failed to connect to the docker API` | Docker Desktop not running | Start it, wait for "Engine running" |
| Build killed / `exit 137` | Out of memory | Close other apps, build one image at a time, raise WSL memory |
| `tls: bad record MAC` or TLS errors while pulling/downloading | Flaky network | Retry; the model cache and layer cache keep partial progress |
| IAM container exits at start | Missing/short required variable | `docker logs auth-service`; see `ENVIRONMENT.md` section 5 |
| Social login: `Untrusted base URL override` | Gateway origin missing from IAM `CORS_ORIGINS` | Add it, recreate `auth-service` |
| Every RAG request 401 in the browser | Not logged in, or `IAM_BASE_URL` wrong | Log in again; check `IAM_BASE_URL` points to the gateway |
| Every RAG request 503 `Could not reach the IAM service` | Gateway/IAM down or wrong URL | Start the core stack; use `host.docker.internal` inside containers |
| Upload 400 `Missing gateway signature` | `FILE_UPLOAD_HMAC_SECRET` missing or different | Set equal values in RAG `.env` and the upload service, recreate both |
| Upload rejected for file type | `ALLOWED_MIME_TYPES` in the upload service | Add the type, recreate `file-upload-service` |
| Invitation email never arrives | Mailpit not on `utility-network`, or wrong `EMAIL_HOST` | Steps 3 and `.env.app`; check `docker logs notification-worker` |
| Chat hangs then 500 `Can't load the model ...cross-encoder...` | Reranker download failed | Step 6, or `ENABLE_RERANKING=false` |
| Chat 500 and logs show `503 ... high demand` | The LLM provider is overloaded | Retry later or switch `LLM_PROVIDER` / `LLM_MODEL` |
| `relation "..." does not exist` | Migrations not applied | Step 5 |
| Frontend shows an error page after editing `.env.local` | Dev server needs a restart | Stop and rerun `npm run dev` |
| Host-run tests can't reach Postgres/Redis | `.env` uses container hostnames | `tests/conftest.py` maps them to localhost:5442 / 6389 automatically; make sure the RAG Postgres/Redis containers are running |

---

## 6. Production notes (short)

Production env files for the infra stacks are generated by `scripts/generate-env.sh` from GitHub Actions secrets and deployed manually with the **deploy-infra** workflow. The secrets to add are listed in `ENVIRONMENT.md` section 10 (notably `BACKUP_CODE_ENCRYPTION_KEY`). The RAG API and frontend are not yet part of that generator; give them the settings in 1.6 / 1.7 with `AUTH_REQUIRED=true`, `APP_ENV=production`, `DEBUG=false`, HTTPS, and real secrets.
