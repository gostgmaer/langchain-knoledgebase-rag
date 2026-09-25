# The other EasyDev services - dependencies and setup

[`SERVICE_DEPENDENCIES.md`](SERVICE_DEPENDENCIES.md) covers what the **RAG project** needs (IAM, gateway, notification, file-upload). This document covers **everything else in the workspace**: what each remaining service depends on, what it needs configured, and how it is started. Use it when you want to run one of them, or the whole platform.

Facts come from the compose files in `easydev-infra/stacks/*`, each service's `.env.example`, the infra env examples, and the gateway's config validation. Anything not confirmed from those is marked **(assumed)**. None of these services were started while writing this, so nothing here is marked as run-verified.

The RAG project does **not** need any service in this document.

---

## 1. Inventory

| Service | Repo (under `WorkSpace`) | Stack | Host port | Purpose |
|---|---|---|---|---|
| payment-service + payment-worker | `Backend/payment-microservice` | core | 3302 | Payments (Stripe / Razorpay), subscriptions |
| lead-microservice | `Backend/lead-microservice` | core | 3305 | Lead capture |
| ai-automation-communication-service | `Product/ai automation communication/backend` | product | 3303 | AI sales/communication automation (email, WhatsApp) |
| job-agent-service | `Product/job-agent-service/backend` | product | 3306 | Job search agent |
| support-ai-api / -webhook / -worker | `Backend/easydev-support-ai` | support-ai | 3307 | Customer-support AI platform |
| ai-workflow-api / -worker | `Backend/multi-tennet-ai-agent` | ai-platform | 8000 | Multi-tenant AI workflow platform (LLM routing) |
| Frontends | `UI/easydev`, `UI/easydev-support-ai-web`, `UI/kishor-portfolio`, `Product/ai automation communication/frontend`, `Product/job-agent-service/web` | - | - | Web UIs |
| Edge / observability | `easydev-infra/stacks/infra` | infra | 80, 443 | Traefik, Portainer, VictoriaMetrics/Logs, Alertmanager (production) |
| CI | `deployment/jenkins` | - | - | Jenkins image and pipelines |

Every backend authenticates users through IAM (`auth-service`) and most reach the outside world through the **gateway**. So **core (Postgres, pgbouncer, Redis, IAM, gateway) is a prerequisite for all of them.**

---

## 2. Stacks, databases and networks

Each stack is a separate compose project with its **own** Postgres, PgBouncer (where used) and Redis, joined over shared external Docker networks.

| Stack (project) | Compose file | Contains | Own databases (host port) |
|---|---|---|---|
| `easydev-core` | `stacks/core/docker-compose.local.build.yml` | auth-service, auth-worker, gateway, gateway-worker, payment-service, payment-worker, lead-microservice | `core-postgres` 5432, `core-redis` 6379 (+ `core-pgbouncer`) |
| `easydev-product` | `stacks/product/...` | ai-automation-communication-service, job-agent-service | `product-postgres` 5434, `product-redis` 6380 (+ `product-pgbouncer`) |
| `easydev-ai-platform` | `stacks/ai-platform/...` | ai-workflow-api, ai-workflow-worker | `ai-platform-postgres` 5436, `ai-platform-redis` 6382 |
| `easydev-support-ai` | `stacks/support-ai/...` | support-ai-api, support-ai-webhook, support-ai-worker | `support-ai-postgres` 5435, `support-ai-redis` 6381 |
| `easydev-utility` | `stacks/utility/...` | notification-service/worker, file-upload-service, utility-redis | `utility-redis` 6383 (and **external MongoDB**) |
| `infra` | `stacks/infra/docker-compose.yml` | Traefik, Portainer, VictoriaMetrics, Logs, Alertmanager, ... | - (production only) |

External networks that must exist (created automatically by `deploy-local.sh`): `core-network`, `product-network`, `ai-platform-network`, `utility-network` (and `support-ai-network` inside its own stack).

**Cross-stack ordering is not automatic.** Compose `depends_on` only works inside one project. `scripts/deploy-local.sh` encodes the order: **core -> product -> ai-platform -> support-ai -> utility.**

---

## 3. Per-service dependencies

Legend: **RUN** = must be up (compose `depends_on` or hard runtime). **CONFIG** = address/secret must be set to boot. **FEATURE** = only that feature breaks when down.

### 3.1 payment-service and payment-worker (`Backend/payment-microservice`, port 3302)

| | |
|---|---|
| **RUN** | `core-pgbouncer` + Postgres (schema `payment`), `core-redis`, **`auth-service`** (`IAM_SERVICE_URL`). Worker also needs `payment-service`. |
| **CONFIG** | `DATABASE_URL`, `REDIS_*`, `IAM_SERVICE_URL`, `JWT_PUBLIC_KEY` (or `JWT_JWKS_URI`) to verify IAM tokens, `API_KEY_HASH` (SHA-256 of the key the gateway sends). |
| **FEATURE** | Stripe (`STRIPE_*`, `STRIPE_ENABLED`) and Razorpay (`RAZORPAY_*`, `RAZORPAY_ENABLED`) - each provider only when enabled and keyed; file-upload (`FILE_UPLOAD_SERVICE_URL`, `FILE_UPLOAD_HMAC_SECRET`) for invoices/attachments; notification (`NOTIFICATION_SERVICE_URL`, `NOTIFICATION_SERVICE_API_KEY`) for receipts. |
| **Needed by** | Gateway (`PAYMENT_SERVICE_URL`, `PAYMENT_SERVICE_API_KEY` - the plaintext whose SHA-256 must equal `API_KEY_HASH`), support-ai (`PAYMENT_SERVICE_URL`). |
| **External accounts** | Stripe and/or Razorpay (test keys locally). |

### 3.2 lead-microservice (`Backend/lead-microservice`, port 3305)

| | |
|---|---|
| **RUN** | `core-redis`, **`auth-service`** (compose), **MongoDB** (`MONGODB_URI`, shared platform Mongo). |
| **CONFIG** | `MONGODB_URI`, `DASHBOARD_URL`, `ALLOWED_ORIGINS`, `LEAD_ENCRYPTION_KEY`. |
| **FEATURE** | notification-service (`EMAIL_SERVICE_URL`, lead emails), file-upload-service (`FILE_UPLOAD_SERVICE_URL`, attachments). |
| **Needed by** | Gateway / the portfolio site (`LEAD_GATEWAY_URL`). |

### 3.3 ai-automation-communication-service (`Product/ai automation communication/backend`, port 3303)

| | |
|---|---|
| **RUN** | `product-pgbouncer` + Postgres, `product-redis`. Users are authenticated by IAM (`IAM_SERVICE_URL`, `IAM_PUBLIC_HOST`, `JWT_PUBLIC_KEY`, `SSO_SECRET`), so **core** must be up for logins. |
| **CONFIG** | `DATABASE_URL` / `DB_*`, `REDIS_*`, `IAM_SERVICE_URL`, `JWT_PUBLIC_KEY`, `COOKIE_SECRET`, `JWT_SECRET`, `SSO_SECRET`, `ENCRYPTION_KEY`, `SALES_API_KEY` (**must equal the gateway's `COMMUNICATION_API_KEY`**), `WEBHOOK_SECRET`, `EASYDEV_API_URL` (the gateway, `http://gateway:3000/api`). |
| **FEATURE** | **MongoDB** (`MONGODB_URI`); notification-service (`NOTIFICATION_SERVICE_URL/_API_KEY`); file-upload-service (`FILE_UPLOAD_SERVICE_URL`); **LLM providers** (`GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `CEREBRAS_API_KEY`, `OPENAI_API_KEY` - the AI router needs at least one); email-account OAuth (Google, Microsoft, Zoho, Yahoo client IDs/secrets); WhatsApp (`WHATSAPP_*`, verify token, app secret); SMTP. |
| **Needed by** | Gateway (`COMMUNICATION_URL`, provisioning), job-agent (`COMMUNICATION_URL`), its own frontend. |

### 3.4 job-agent-service (`Product/job-agent-service/backend`, port 3306)

| | |
|---|---|
| **RUN** | `product-pgbouncer` + Postgres (schema `api_job_agent`), `product-redis`; **core** for IAM logins. |
| **CONFIG** | `DATABASE_URL`, `REDIS_*`, `IAM_SERVICE_URL`, `JWT_PUBLIC_KEY`, `COOKIE_SECRET`, `SSO_SECRET`, `ENCRYPTION_KEY`, `JOB_AGENT_API_KEY` (**must equal the gateway's `JOB_AGENT_API_KEY`**, sent as `X-Api-Key`). |
| **FEATURE** | **ai-workflow-api** (`AI_PLATFORM_BASE_URL`, `AI_PLATFORM_SIGNING_SECRET` + key version - the signing secret must match the AI platform's `AI_PLATFORM_REQUEST_SIGNING_SECRETS__v1`); the communication service (`COMMUNICATION_URL`); notification and file-upload (`FILE_UPLOAD_HMAC_SECRET`); a job-listings API (`ADZUNA_APP_KEY`). |
| **Needed by** | Gateway (`JOB_AGENT_URL`), its own web UI. |

### 3.5 support-ai (`Backend/easydev-support-ai`: api port 3307, webhook, worker)

| | |
|---|---|
| **RUN** | `support-ai-postgres`, `support-ai-redis`; `support-ai-webhook` and `support-ai-worker` need `support-ai-api`. **IAM** (`IAM_SERVICE_URL`, `IAM_SERVICE_INTERNAL_URL`, `IAM_SERVICE_API_KEY`). |
| **CONFIG** | `DATABASE_URL`, `REDIS_*`, `IAM_SERVICE_URL`, and the secret set: `ENCRYPTION_KEY`, `COOKIE_SECRET`, `CONNECTOR_ENCRYPTION_KEY`, `WIDGET_JWT_SECRET`, `ADMIN_WEBHOOK_ENCRYPTION_KEY`, `ADMIN_API_KEY_HASH_SECRET`. |
| **FEATURE** | **ai-workflow-api** (`EASYDEV_AI_URL`, `EASYDEV_AI_API_KEY`) - AI answers; payment-service (`PAYMENT_SERVICE_URL`, `PAYMENT_SERVICE_API_KEY`, `PAYMENT_IAM_CLIENT_SECRET`) - billing; notification; file-upload (`FILE_UPLOAD_HMAC_SECRET`). |
| **Needed by** | Gateway (`SUPPORT_AI_URL`, key must match the support-ai admin key material), the support-ai web UI and embeddable widget. |

### 3.6 ai-workflow platform (`Backend/multi-tennet-ai-agent`: api port 8000, worker)

| | |
|---|---|
| **RUN** | `ai-platform-postgres`, `ai-platform-redis`; worker needs `ai-workflow-api`. |
| **CONFIG** | `AI_PLATFORM_DATABASE_URL`, `AI_PLATFORM_REDIS_URL`, `AI_PLATFORM_REQUEST_SIGNING_SECRETS__v1` (shared with every caller), `AI_PLATFORM_SECURITY_ENCRYPTION_KEYS__*` (+ active key version), at least one provider (`AI_PLATFORM_PROVIDER_API_KEYS__<provider>`, `AI_PLATFORM_DEFAULT_PROVIDER`). |
| **FEATURE** | An LLM provider. The bundled local config uses **Ollama** (`ollama serve` on the host, e.g. model `qwen3:14b`) so no cloud key is needed; production uses cloud providers with fallback, rate limits and circuit breakers. |
| **Does not call IAM** for its own auth (callers sign requests with the shared secret) **(assumed)**. |
| **Needed by** | Gateway (`AI_WORKFLOW_URL`), job-agent, support-ai. |

### 3.7 Frontends

| App | Talks to | Key variables |
|---|---|---|
| `UI/easydev` (Next 14) | Gateway / dashboard, chat widget | `NEXT_PUBLIC_BASE_URL`, `NEXT_PUBLIC_DASHBOARD_BASE_URL`, `NEXT_PUBLIC_TENANT_SLUG`, `NEXT_PUBLIC_TENANT_ID`, `NEXT_PUBLIC_CHAT_WIDGET_*` |
| `UI/easydev-support-ai-web` | support-ai API, IAM | own env (no example file found) **(assumed)** |
| `UI/kishor-portfolio` (Next 14) | notification-service, lead gateway, MongoDB | `NOTIFICATION_SERVICE_URL/_API_KEY`, `MONGODB_URI`, `LEAD_GATEWAY_URL`, `LEAD_TENANT_ID` |
| communication `frontend` (Next 14) | communication backend + socket | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SOCKET_URL`, `NEXT_PUBLIC_EASYDEV_URL/_API_URL` |
| `job-agent-service/web` (Next 15) | job-agent backend | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_EASYDEV_URL` |

The RAG frontend (`langchain-knoledgebase-rag/frontend`) is separate; see `ENVIRONMENT.md` section 4.

### 3.8 Edge, observability and CI

- **`stacks/infra`** (Traefik on 80/443, Portainer, docker-socket-proxy, Vector, VictoriaLogs, VictoriaMetrics, vmagent, vmalert, Alertmanager): production reverse proxy and monitoring. **Not needed locally.** Internal dependencies: `vector` -> `docker-socket-proxy` + `victorialogs`; `vmagent` -> `victoriametrics`; `vmalert` -> `victoriametrics` + `alertmanager`.
- **Jenkins** (`deployment/jenkins`): its own `docker-compose.yml`, `Dockerfile`, `jenkins.yaml`, `plugins.txt`; see `jenkins_cicd_platform_guide.md` in that folder.

---

## 4. Secrets that must match across services

| Value | Set in | Must equal | If wrong |
|---|---|---|---|
| Postgres password | `.env.shared` / `.env.postgres` (each stack) | the password inside every `DATABASE_URL` of that stack | service crash-loops on DB auth |
| Redis password | `.env.shared` / `.env.redis` | the password inside every `REDIS_URL` of that stack | same |
| `COMMUNICATION_API_KEY` (gateway) | `.env.gateway` | `SALES_API_KEY` in the communication service | gateway cannot call communication |
| `JOB_AGENT_API_KEY` (gateway) | `.env.gateway` | `JOB_AGENT_API_KEY` in job-agent | gateway cannot call job-agent |
| `PAYMENT_SERVICE_API_KEY` (gateway, plaintext) | `.env.gateway` | SHA-256 of it = `API_KEY_HASH` in payment | payment rejects the gateway. Only the gateway holds the plaintext. |
| `AI_WORKFLOW_SIGNING_SECRET` (gateway), `AI_PLATFORM_SIGNING_SECRET` (job-agent), `EASYDEV_AI_API_KEY` (support-ai) | each caller | `AI_PLATFORM_REQUEST_SIGNING_SECRETS__v1` in the AI platform | AI calls rejected |
| `SUPPORT_AI_API_KEY` (gateway) | `.env.gateway` | the admin API key material in support-ai (`ADMIN_API_KEY_HASH_SECRET`) | gateway cannot call support-ai |
| `IAM_ADMIN_EMAIL` / `IAM_ADMIN_PASSWORD` (gateway) | `.env.gateway` | IAM `BOOTSTRAP_SERVICE_ACCOUNT_*` | gateway cannot provision users/tenants in IAM |
| `FILE_UPLOAD_HMAC_SECRET` | payment, job-agent, support-ai, IAM, RAG | the upload service's `GATEWAY_INTERNAL_SECRET` | 401 `Missing gateway signature` |
| `NOTIFICATION_SERVICE_API_KEY` / `NOTIFICATION_API_KEY` | every caller | notification-service `API_KEY` | no email |
| `JWT_PUBLIC_KEY` | payment, communication, job-agent (and any verifier) | IAM's public key | IAM tokens rejected |

Full variable lists for core/utility services: `ENVIRONMENT.md`. For the services in this document, each repo's `.env.example` and `stacks/<stack>/env/.env.*.example` are the source of truth.

---

## 5. Notification and file-upload are local - endpoints to use

Both services run locally, so every service must point at them, not at the old hosted deployments (a Vercel notification service and a Render upload service). Use:

| Caller runs... | Notification | File upload |
|---|---|---|
| **Inside Docker** (infra stacks; templates in `stacks/*/env/*.example`) | `http://notification-service:4000/v1` (health `.../v1/health`) | `http://file-upload-service:3000` (health `.../health`) |
| **From source on your machine** (each repo's own `.env`) | `http://localhost:4004/v1` | `http://localhost:4005` |
| **RAG API inside Docker** (reaches the host) | not used | `http://host.docker.internal:4005` |

Keep any path suffix a service already appends (some use `.../v1`, some add it themselves). The shipped examples for the core, product and support-ai stacks and the per-repo `.env` files have been switched to these values. Still hosted by default (production only, left as is): `scripts/secrets.example.env`, `scripts/github-config.env`, `Backend/web-agency-backend-api/deploy/oracle-vm/*`, `UI/easydev/docker-compose.yml`, and the gateway's built-in fallback for `FILE_UPLOAD_SERVICE_URL` (if that variable is unset the gateway silently uses the hosted Render URL, so always set it).

---

## 6. How to start them

Everything below uses `scripts/deploy-local.sh` from `easydev-infra` (builds every image from local source, applies migrations/seeds, creates the networks, waits for health). **Always start core first.**

```bash
cd "/c/Users/kisho/WorkSpace/docker network/easydev-infra"

bash scripts/deploy-local.sh --stack core                 # core incl. payment + lead
bash scripts/deploy-local.sh --stack product              # communication + job-agent
bash scripts/deploy-local.sh --stack ai-platform          # AI workflow (start before support-ai and job-agent's AI features)
bash scripts/deploy-local.sh --stack support-ai
bash scripts/deploy-local.sh --stack utility              # notification + file-upload (+ provide MongoDB)

bash scripts/deploy-local.sh                              # all stacks, in the right order
bash scripts/deploy-local.sh --fresh --stack product      # wipe that stack's data volumes and re-seed
```

Other flags: `--no-build`, `--no-cache`, `--follow`, `--quiet-build`, `--core-only`. `--stack` assumes the stacks a service depends on are already running. Read-only checks afterwards: `bash scripts/verify-stack.sh`.

Build one image at a time on a low-memory machine (large builds were OOM-killed here).

### What to start for each goal

| Goal | Start |
|---|---|
| Payments | core (`auth-service`, gateway) + `payment-service`, `payment-worker`; provider test keys |
| Leads | core + `lead-microservice` + MongoDB (+ utility for email) |
| AI communication | core + product stack + MongoDB + utility + at least one LLM key |
| Job agent | core + product stack + ai-platform (for AI features) + utility |
| Support AI | core + support-ai stack + ai-platform + utility (+ payment for billing) |
| AI workflow only | ai-platform stack + an LLM (Ollama locally) |
| A frontend | its backend, plus core (gateway, IAM) for sign-in |
| Everything | `bash scripts/deploy-local.sh` |

---

## 7. Reverse view - "if I stop X, what breaks?"

| Stop... | Breaks |
|---|---|
| core Postgres / pgbouncer / Redis / **IAM** / **gateway** | every backend's logins and gateway routes; payment and lead do not even start (compose depends on `auth-service`) |
| product Postgres / pgbouncer / Redis | communication, job-agent |
| ai-platform stack | AI features in job-agent, support-ai, gateway `/ai` routes; nothing else |
| support-ai stack | support-ai only |
| payment-service | billing in the gateway and support-ai |
| utility stack (notification/upload) or MongoDB | emails and file uploads across all services; lead, communication and the portfolio site also lose MongoDB |
| infra stack | production routing/monitoring only |

---

## 8. Not verified

- None of these services were started while writing this. Everything comes from compose files, env examples and config code.
- The exact local-network path from product/support-ai services to notification and file-upload (section 5) should be confirmed when you first run them.
- Variable lists are grouped by dependency, not exhaustive; the `.env.example` in each repo is authoritative.
