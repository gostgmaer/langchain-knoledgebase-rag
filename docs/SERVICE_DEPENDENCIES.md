# Service dependencies - what each service needs, and what needs it

Answers, per service: *"what must be running (or configured) before this starts, what stops working if a dependency is down, and which services depend on this one?"* Companion to [`LOCAL_SETUP.md`](LOCAL_SETUP.md) (how to start everything) and [`ENVIRONMENT.md`](ENVIRONMENT.md) (every variable).

Source of the facts below: the compose `depends_on` entries, each service's config validation and env files, and grep of the code that makes the outbound calls. Where something could not be confirmed from code it is marked **(assumed)**.

## 0. Three kinds of dependency (read this first)

| Kind | Meaning | Example |
|---|---|---|
| **RUN** (hard) | The dependency must be up and reachable, or this service fails to start or its core function fails. | gateway -> IAM |
| **CONFIG** | The dependency's *address* must be set (a required, valid URL variable) or this service refuses to boot, but the dependency does **not** have to be running for it to boot. | IAM -> `NOTIFICATION_SERVICE_URL` |
| **FEATURE** (soft) | Only one feature breaks (usually with a logged error, not a crash) when it is down. | IAM -> notification (emails) |

This distinction answers most "do I really need X to run Y?" questions: **Y often needs X's URL configured, but only needs X running for the feature that uses it.** For a complete, working system (all features usable) you run all of them.

---

## 1. Dependency map

```
                        +-----------------------+
   Browser  ----------> |  Frontend  (:3000)    |
                        +-----+-----------+-----+
                  /api/auth,/api/iam       /api/rag (adds Bearer token)
                              |                 |
                              v                 v
                      +--------------+   +-----------------+   LLM / embeddings (Gemini, ...)
                      |  Gateway     |   |  RAG API (:8088)|-----> external, needed for chat
                      |  (:3301)     |   +--+-----+-----+--+
                      +------+-------+      |     |     |
                             | RUN          |     |     +--> RAG Postgres+pgvector (:5442)  RUN
                             v              |     +--------> RAG Redis (:6389)              RUN
                      +--------------+      |
                      |  IAM auth-   | <----+ RUN when AUTH_REQUIRED=true (via the gateway: GET /auth/me)
                      |  service     |
                      |  (:3304)     |      RAG worker --> RAG Postgres, RAG Redis, file-upload (download), LLM
                      +--+---+---+---+
              RUN        |   |   |  FEATURE                      FEATURE
        +----------------+   |   +--------------------+-----------------------+
        v                    v                        v                       v
  core-pgbouncer -> core-postgres     core-redis   notification-service   file-upload-service
        (RUN)                          (RUN)        (:4004)                (:4005)
                                                    |  RUN     |  RUN        |  RUN
                                                    v          v             v
                                              utility-redis   Mongo   <----- Mongo (also RUN)
                                                    |
                                                    v RUN (to actually deliver mail)
                                          SMTP server (Mailpit :1025 locally)
```

RAG also calls **file-upload-service** directly (documents), not through IAM.

---

## 2. Per-service reference

### 2.1 IAM auth-service (`auth-service`, port 3304) and `auth-worker`

| | |
|---|---|
| **RUN** | `core-postgres` via `core-pgbouncer` (schema `iam`); `core-redis`. Compose: `depends_on core-pgbouncer, core-redis`. |
| **CONFIG** (required to boot) | `NOTIFICATION_SERVICE_URL`, `FILE_UPLOAD_SERVICE_URL` (valid URLs), `FRONTEND_URL`, `AUTH_PUBLIC_BASE_URL`, secrets (`COOKIE_SECRET`, `SSO_SECRET`, `JWT_REFRESH_SECRET`, `JWT_MAGIC_LINK_SECRET`), plus `BACKUP_CODE_ENCRYPTION_KEY` and, in production, `CORS_ORIGINS`. |
| **FEATURE** | **notification-service** - every email IAM sends (invitations, verification, "social account connected"). Calls have an 8 s timeout and are wrapped in try/catch, so IAM keeps working and only the email is lost. **file-upload-service** - profile avatars only. Kafka - off unless `ENABLE_KAFKA=true`. |
| **Does not need** | The gateway, the RAG stack, or the frontend. IAM can run and be tested with plain HTTP (`curl`) on its own port. |
| **Needed by** | Gateway (RUN), RAG API (RUN when `AUTH_REQUIRED=true`), frontend (through the gateway), and every other product service. |
| `auth-worker` | Same image, BullMQ consumer (webhooks, domain events, notification jobs). RUN: same DB/Redis and `auth-service` (compose `depends_on`). |
| **If it is down** | Nobody can sign in; RAG returns 503 for every request (`AUTH_REQUIRED=true`); the frontend cannot log in. |

**To run IAM alone:** `core-postgres`, `core-pgbouncer`, `core-redis`, then `auth-service`. Set the two service URLs even though nothing answers on them. Login, users, roles, tenants and token issuing all work. Invitations "succeed" but no email is sent; a warning is logged.

**To run IAM with all its features:** add notification-service + its worker + utility-redis + MongoDB + an SMTP server (Mailpit locally), and file-upload-service + MongoDB.

### 2.2 API gateway (`gateway`, port 3301) and `gateway-worker`

| | |
|---|---|
| **RUN** | `auth-service` (compose `depends_on`); Redis (`REDIS_URL` is required and used for cache, database index 3). |
| **CONFIG** (required to boot) | `AUTH_SERVICE_URL`, `FRONTEND_URL`, `DASHBOARD_URL`, `REDIS_URL`, and service URLs it validates at startup even for products you do not run: `COMMUNICATION_URL` and `PAYMENT_SERVICE_URL` (placeholders are fine; those services do **not** need to be running). |
| **WARNING** | `FILE_UPLOAD_SERVICE_URL` is not required by the gateway, but if it is **unset the gateway silently falls back to a hosted Render URL** (`file-upload-service-zjtv.onrender.com`) instead of your local service. Always set it locally (`http://file-upload-service:3000`). |
| **FEATURE** | notification-service (mail it sends itself), product services (communication, payment, job-agent, support-ai, AI workflow) - only for their routes. |
| **OPTIONAL** | MongoDB - the code logs a note and runs without it locally when `MONGODB_URI` is empty. Required in production. |
| **Needed by** | Frontend (`/api/auth/*`, `/api/iam/*` for invitations and connected accounts) and the RAG API (its `IAM_BASE_URL` points here). |
| `gateway-worker` | Background jobs; RUN: `auth-service` and `gateway`. |
| **If it is down** | The UI cannot log in or manage users; RAG cannot verify tokens (503). IAM itself is unaffected. |

**To run the gateway alone:** you cannot usefully - it needs IAM running. Minimum: IAM's set + gateway + Redis.

### 2.3 notification-service (`notification-service`, port 4004) and `notification-worker`

| | |
|---|---|
| **RUN** | `utility-redis` (BullMQ queues; compose `depends_on`); MongoDB (email logs, templates, OTP store); an SMTP server to actually deliver mail (Mailpit locally). |
| **CONFIG** | `API_KEY` (callers send it as `x-api-key`), `MONGODB_URI`, `REDIS_URL`/`REDIS_PASSWORD`, `EMAIL_*`. |
| **Calls other services?** | No. It does not call IAM, the gateway, or the upload service (no such calls in its source). |
| **Needed by** | IAM (invitation/verification/connected-account mail) and the gateway. RAG does **not** call it directly. |
| `notification-worker` | Consumes the queue and sends the mail. RUN: `utility-redis`, `notification-service`. **The API can accept a request while the worker is stopped: the mail then just sits in the queue.** |
| **If it is down** | No emails; IAM keeps working. |

**To run it alone:** `utility-redis` + MongoDB + `notification-service` + `notification-worker` + Mailpit. Test with `POST http://localhost:4004/v1/...` and header `x-api-key`.

### 2.4 file-upload-service (`file-upload-service`, port 4005)

| | |
|---|---|
| **RUN** | MongoDB (`MONGO_URI`, validated at boot); a storage backend (`local` volume, or R2 / Azure / S3 / GCS with credentials). |
| **OPTIONAL** | Redis (`REDIS_URL`, only for distributed rate limiting); ClamAV (virus scanning) if `CLAMAV_HOST` is set. |
| **CONFIG** | `GATEWAY_INTERNAL_SECRET` (32+ chars, required while `GATEWAY_AUTH_REQUIRED=true`), `LOCAL_SIGNED_URL_SECRET` (32+ chars, when storage is `local`). |
| **Calls other services?** | No runtime calls to IAM or the gateway. It trusts callers that present a valid `X-Gateway-Hmac` signature made with the shared secret. |
| **Needed by** | RAG API and worker (documents), IAM (avatars), gateway. |
| **If it is down** | RAG document upload returns 502; ingestion of already-queued jobs fails when the worker cannot download the file. Chat over already-ingested documents still works (the text and embeddings live in the RAG database). |

**To run it alone:** MongoDB + storage + the service. It needs no other EasyDev service.

### 2.5 RAG API (`api`, port 8088)

| | |
|---|---|
| **RUN** | RAG Postgres with pgvector (`postgres`), RAG Redis (`redis`). Migrations applied (`alembic upgrade head`). |
| **RUN when `AUTH_REQUIRED=true`** | The **gateway** and **IAM** (each request is verified with `GET {IAM_BASE_URL}/api/auth/me`). With `AUTH_REQUIRED=false` it falls back to an anonymous default tenant and does not need them. |
| **FEATURE** | LLM provider (chat, and embeddings during ingestion) - external and rate-limited; **file-upload-service** for `POST /documents`; HuggingFace (first-run download of the reranker model, then cached); optional Jaeger, LangSmith. |
| **CONFIG** (required to boot) | `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `IAM_BASE_URL`, `IAM_CLIENT_ID`, `IAM_CLIENT_SECRET`, `IAM_INTROSPECTION_API_KEY`, `UPLOAD_SERVICE_URL`, `OPENWEATHER_API_KEY`, `NEWSAPI_API_KEY`. |
| **Does not need** | notification-service (the RAG code never calls it). |
| **Needed by** | Frontend (through the `/api/rag` proxy). |
| **If IAM/gateway is down** | Every request returns 503 (`AUTH_REQUIRED=true`). |

### 2.6 RAG worker (`worker`)

| | |
|---|---|
| **RUN** | RAG Postgres, RAG Redis (the job queue). |
| **FEATURE** | file-upload-service (downloads the document), LLM/embedding provider (embeds chunks). |
| **Needed by** | The RAG API enqueues ingestion jobs; nothing happens to uploaded documents while the worker is stopped (they stay `QUEUED`). |

### 2.7 Frontend (`frontend/`, port 3000)

| | |
|---|---|
| **RUN** | The gateway (login, session, invitations, connected accounts) and the RAG API (`RAG_API_URL`, via the `/api/rag` proxy). |
| **Transitively** | IAM, and everything the RAG API needs. |
| **Needs no database of its own** | Sessions are httpOnly cookies holding IAM tokens. |
| **If the gateway is down** | Login fails and social buttons disappear (the providers lookup fails closed). |

### 2.8 Shared infrastructure

| Component | Used by | Notes |
|---|---|---|
| `core-postgres` (+ `core-pgbouncer`) | IAM (schema `iam`) | pgbouncer must be healthy; IAM connects through it. |
| `core-redis` | IAM, gateway | |
| `utility-redis` | notification-service and worker | Separate from core Redis. |
| **MongoDB** (external) | notification-service, file-upload-service, gateway (optional locally) | Not started by any compose file - provide it yourself. |
| Mailpit / SMTP | notification-service | Local mail catcher on the `utility-network`. |
| RAG `postgres` (pgvector) + `redis` | RAG API and worker only | Independent of the EasyDev databases. |
| Jaeger | RAG API (optional) | Trace viewer only. |

---

## 3. "Who needs me?" (reverse view)

| If you stop... | ...these break |
|---|---|
| core Postgres / pgbouncer / core Redis | IAM -> gateway -> everything else |
| **IAM auth-service** | Gateway (compose dependency), all logins, all RAG requests (503) |
| **Gateway** | Frontend login and user management, RAG token verification |
| notification-service (or its worker, or Redis/Mongo behind it) | Emails only (invites, verification). IAM keeps running. |
| file-upload-service (or its MongoDB) | RAG document upload and ingestion, IAM avatars. Existing RAG content stays searchable. |
| RAG Postgres / Redis | RAG API and worker |
| RAG worker | New documents never finish ingesting |
| The LLM provider | Chat answers (500), and embedding during ingestion |
| MongoDB | notification-service and file-upload-service (and so emails and uploads) |

---

## 4. Which services to start for each goal

| Goal | Start |
|---|---|
| Just IAM (API testing, no emails) | core Postgres, pgbouncer, core Redis, `auth-service` |
| IAM with emails | + utility Redis, MongoDB, Mailpit, `notification-service`, `notification-worker` |
| IAM with avatars | + MongoDB, `file-upload-service` |
| Login page + user management in the UI | IAM (above) + `gateway` + frontend |
| Invite a user and receive the email | + notification set (above) |
| RAG API without auth (`AUTH_REQUIRED=false`) | RAG Postgres, RAG Redis, RAG API (+ worker for ingestion) |
| RAG with real accounts | + IAM + gateway |
| Upload and ingest documents | + `file-upload-service` (+ MongoDB) + RAG worker + an LLM key |
| Chat with citations | + LLM provider + reranker model cached |
| **Everything (the full product)** | MongoDB, core Postgres/pgbouncer/Redis, `auth-service`, `auth-worker`, `gateway`, `gateway-worker`, utility Redis, `notification-service`, `notification-worker`, Mailpit, `file-upload-service`, RAG Postgres/Redis, RAG `api` + `worker`, frontend |

## 5. Feature-by-feature: exactly which services are involved

| Feature | Services that must be running |
|---|---|
| Email/password login | frontend, gateway, IAM, core Postgres/pgbouncer/Redis |
| Register a new account | same as login (+ notification for the verification email) |
| Admin invites a user / user accepts | frontend, gateway, IAM, core DB/Redis, **notification + worker + utility Redis + MongoDB + SMTP** |
| Social login and connected accounts | frontend, gateway, IAM, core DB/Redis, the provider (Google/Microsoft/Facebook), and notification for the "account connected" email |
| Every RAG page (agents, prompts, knowledge bases...) | frontend, gateway, IAM, RAG API, RAG Postgres/Redis |
| Document upload and ingestion | the row above + **file-upload-service + MongoDB + RAG worker + embedding provider** |
| Chat with answers and citations | RAG page row + LLM provider + reranker model (cached in the `hf-cache` volume) |
| Team page role list | frontend, gateway, IAM |

## 6. Start-order rules (why the order in the runbook is what it is)

1. **Databases and caches first.** IAM will not become healthy without pgbouncer and Redis; notification will not without utility Redis and MongoDB.
2. **IAM before the gateway.** The compose file makes the gateway wait for `auth-service`; a gateway that starts first would crash-loop.
3. **Notification and file-upload can start before or after IAM.** IAM only needs their URLs configured, and retries per request. Start them **before you test** invitations or uploads, otherwise those particular actions fail with a logged error.
4. **RAG API after IAM and the gateway** when `AUTH_REQUIRED=true` (otherwise its first requests return 503 until they are up).
5. **Frontend last** - it only proxies to the others.
6. **Cross-stack ordering is not automatic**: `depends_on` works inside one compose project only. That is why `scripts/deploy-local.sh` starts the stacks (core, then utility) in a fixed order, and why the runbook does the same by hand.

## 7. Things that look like dependencies but are not

- RAG -> notification: **no**. Only IAM sends email.
- IAM -> gateway: **no**. The gateway calls IAM, not the other way round (IAM only knows its own `AUTH_PUBLIC_BASE_URL` and the trusted `CORS_ORIGINS`, which must include the gateway's origin for social-login callbacks).
- Notification -> IAM, file-upload -> IAM: **no runtime call**. They share secrets/keys with their callers, not sessions.
- RAG -> payment, lead, job-agent, support-ai, communication: **no**. The gateway's config wants their URLs set to *something*, but they never need to run for the RAG project.
- `IAM_JWKS_BASE_URL` in the RAG config: **unused today** (tokens are verified through `/auth/me`).

## 8. Quick self-check after starting

```bash
# core
curl -s -o /dev/null -w "IAM/gateway login  -> %{http_code}\n" -X POST http://localhost:3301/api/auth/login \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:3000' \
  -d '{"email":"<admin>","password":"<password>"}'
# utility
curl -s -o /dev/null -w "notification       -> %{http_code}\n" http://localhost:4004/v1/health/live
curl -s -o /dev/null -w "file-upload        -> %{http_code}\n" http://localhost:4005/health/live
curl -s -o /dev/null -w "mailpit UI         -> %{http_code}\n" http://localhost:8025/
# RAG
curl -s -o /dev/null -w "RAG health         -> %{http_code}\n" http://localhost:8088/api/v1/health
curl -s -o /dev/null -w "RAG anonymous (401)-> %{http_code}\n" http://localhost:8088/api/v1/knowledge-bases
# frontend
curl -s -o /dev/null -w "frontend           -> %{http_code}\n" http://localhost:3000/
```
