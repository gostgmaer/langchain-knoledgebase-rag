# Dependencies - RAG platform (API, worker, frontend)

Retrieval-augmented chat over uploaded documents. API host port 8088 (container 8000), Next.js frontend on 3000.

This file is self-contained: it says what must be running (or configured) before this service works, gives the commands to start those dependencies, and lists who depends on it. `<infra>` below is `easydev-infra` (in this workspace: `C:\Users\kisho\WorkSpace\docker network\easydev-infra`). The full platform map is in this folder: `SERVICE_DEPENDENCIES.md`, `OTHER_SERVICES_DEPENDENCIES.md`, `LOCAL_SETUP.md`, `ENVIRONMENT.md`.

**Legend:** **RUN** = must be up (compose `depends_on` or hard runtime). **CONFIG** = its address/secret must be set for this service to boot, but it need not be running. **FEATURE** = only one feature breaks when it is down. Nothing in this file was re-run when it was written; it is derived from the compose files, env examples and config code.

## 1. What this service depends on

| Dependency | Kind | Why |
|---|---|---|
| RAG Postgres (pgvector) + RAG Redis | RUN | Started by this repo's own compose (`docker compose --profile full up -d`). Apply migrations: `docker compose exec api alembic upgrade head`. |
| gateway and IAM (and IAM's Postgres/pgbouncer/Redis) | RUN when `AUTH_REQUIRED=true` | Every request is verified with `GET {IAM_BASE_URL}/api/auth/me` through the gateway. With `AUTH_REQUIRED=false` the API uses an anonymous default tenant and does not need them. |
| file-upload-service (+ MongoDB) | CONFIG + FEATURE | `UPLOAD_SERVICE_URL` must be set to boot. Needed to upload and ingest documents; uploads fail with `Missing gateway signature` unless `FILE_UPLOAD_HMAC_SECRET` matches the upload service's secret. |
| notification-service (+ worker, utility Redis, MongoDB, Mailpit) | FEATURE (indirect) | The RAG code never calls it. It is needed only because IAM sends invitation/verification email through it. |
| LLM + embedding provider (Gemini by default) | FEATURE | Chat answers and document embedding. Provider outages (503) return HTTP 500 from chat. |
| HuggingFace (first run only) | FEATURE | ~90 MB reranker model, cached afterwards in the `hf-cache` volume; or set `ENABLE_RERANKING=false`. |

**Minimum to run it:** RAG data services + API + worker with `AUTH_REQUIRED=false` needs nothing else. For real accounts add core (IAM + gateway); for document upload add the utility stack + MongoDB; for chat add an LLM key.

## 2. Bring the dependencies up

Create the shared Docker networks once (safe to repeat):

```bash
for n in core-network product-network ai-platform-network utility-network; do
  docker network inspect $n >/dev/null 2>&1 || docker network create $n
done
```

Start in this order (Git Bash; Docker Desktop must be running). Steps marked **(optional)** are only needed for the features noted as FEATURE/CONFIG in section 1; skip them if you do not use those features.

1. **MongoDB (external - no compose file starts it)** **(optional)**

   ```bash
   # Use your existing MongoDB / Atlas, or a throwaway local one:
   docker run -d --name mongo --restart unless-stopped -p 27017:27017 -v mongo-data:/data/db mongo:7
   # URI for containers: mongodb://host.docker.internal:27017/easydev
   ```

2. **Core: databases, IAM, gateway**

   ```bash
   cd "/c/Users/kisho/WorkSpace/docker network/easydev-infra"/stacks/core
   docker compose -p easydev-core -f docker-compose.local.build.yml up -d --build \
     core-postgres core-pgbouncer core-redis auth-service auth-worker gateway gateway-worker
   ```

3. **Utility stack: notification-service (+worker), file-upload-service, utility-redis** **(optional)**

   ```bash
   cd "/c/Users/kisho/WorkSpace/docker network/easydev-infra"/stacks/utility
   docker compose -p easydev-utility -f docker-compose.local.build.yml up -d --build
   ```

4. **Mailpit (local mail catcher; UI http://localhost:8025)** **(optional)**

   ```bash
   docker run -d --name mailpit --restart unless-stopped --network utility-network -p 1025:1025 -p 8025:8025 axllent/mailpit
   ```

5. **RAG backend: Postgres (pgvector), Redis, API, worker**

   ```bash
   cd "/c/Users/kisho/WorkSpace/learning/ai/langchain-knoledgebase-rag"
   docker compose --profile full up -d --build
   ```

6. **This service (learning/ai/langchain-knoledgebase-rag)** - if it is part of one of the stacks above it is already started by that step. To run it from source while developing, keep the dependencies above up and follow this repo's README. Whole-stack shortcut from the infra repo: `bash <infra>/scripts/deploy-local.sh --stack <core|product|ai-platform|support-ai|utility>` (builds from local source, creates the networks, waits for health; `--stack` assumes the stacks it depends on are already running). Build one image at a time on a low-memory machine.

## 3. Settings that tie it to its dependencies

- DATABASE_URL, REDIS_URL, JWT_SECRET (legacy, must be set)
- AUTH_REQUIRED=true (recommended), ADMIN_ROLES
- IAM_BASE_URL=http://host.docker.internal:3301 (the gateway), IAM_CLIENT_ID, IAM_CLIENT_SECRET, IAM_INTROSPECTION_API_KEY
- UPLOAD_SERVICE_URL=http://host.docker.internal:4005, FILE_UPLOAD_HMAC_SECRET, UPLOAD_SERVICE_ROLE
- LLM_PROVIDER, LLM_MODEL, the provider API key, EMBEDDING_*
- OPENWEATHER_API_KEY, NEWSAPI_API_KEY (placeholders allowed, but must be set)
- frontend/.env.local: RAG_API_URL, AUTH_GATEWAY_URL (and AUTH_GATEWAY_PUBLIC_URL if that is an internal host)

Full variable documentation for the RAG-related services: `ENVIRONMENT.md` in the RAG repo. Never commit real values; only `*.example` files are tracked.

## 4. Who depends on this service

- The RAG frontend (through the `/api/rag` proxy)
- Nothing else in the EasyDev platform depends on it

If you stop it, those consumers lose the feature described above.

## 5. Check it is up

```bash
curl -s -o /dev/null -w "RAG health -> %{http_code}\n" http://localhost:8088/api/v1/health
curl -s -o /dev/null -w "anonymous  -> %{http_code}  (expect 401 with AUTH_REQUIRED=true)\n" http://localhost:8088/api/v1/knowledge-bases
```
