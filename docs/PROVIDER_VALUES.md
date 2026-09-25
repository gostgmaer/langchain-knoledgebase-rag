# Provider values you have to supply

Everything that can be generated or defaulted locally (secrets, URLs, ports, flags, local storage, Mailpit) is already set in the local env files. What is left needs an account at an outside provider. This page lists each one: what it is for, where to get it, which file it goes in, and what breaks without it.

Check the live state at any time (key names and `set` / `empty` / `MISSING` only, never values):

```bash
python scripts/preflight_env.py --providers
```

`set` means a value is present, **not that it is valid**. Only a real request proves that. After changing any value, recreate the container that reads it (`docker compose up -d <service>`; a plain restart may not re-read `env_file`), or restart `npm run dev` for the frontend.

Paths: `<infra>` = `C:\Users\kisho\WorkSpace\docker network\easydev-infra`.

---

## A. Needed to test the RAG chat itself

| Value | File | Where to get it | Needed for | Without it |
|---|---|---|---|---|
| `GOOGLE_API_KEY` | RAG `.env` | Google AI Studio (aistudio.google.com) -> Get API key | Chat answers and document embedding (`LLM_PROVIDER=google`, `EMBEDDING_PROVIDER=google`) | Chat and ingestion fail. A key that is set but over quota or unauthorised looks the same, and Gemini 503 "high demand" is temporary, not a key problem. |
| or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | RAG `.env` | The provider console | Alternative LLM: set `LLM_PROVIDER` and `LLM_MODEL` to match (Anthropic has no embeddings; keep `EMBEDDING_PROVIDER` on Google or OpenAI) | - |
| `MongoDB URI` | `<infra>/stacks/utility/env/.env.app` (`MONGODB_URI`) and `.env.file-upload` (`MONGO_URI`) | Atlas (`mongodb+srv://...`) or your own server | Notification and file-upload both store data here | Neither service starts: no invitation email, no document upload |

## B. Optional tools (RAG works without real values)

| Value | File | Where to get it | Notes |
|---|---|---|---|
| `SERPER_API_KEY` or `TAVILY_API_KEY` | RAG `.env` | serper.dev / tavily.com | Web-search tool. Set `ENABLE_WEB_SEARCH=false` if unused. |
| `OPENWEATHER_API_KEY` | RAG `.env` | openweathermap.org | Weather tool. The app needs *a* value to boot; a dummy is fine if `ENABLE_WEATHER=false`. |
| `NEWSAPI_API_KEY` | RAG `.env` | newsapi.org | News tool. Same rule. |
| `LANGCHAIN_API_KEY` | RAG `.env` | smith.langchain.com | LangSmith tracing. If you do not have one, set `LANGCHAIN_TRACING_V2=false`. |

## C. Social login (buttons appear only for providers you configure and enable)

Redirect URI to register at **every** provider (scheme + host = the gateway):

```
http://localhost:3301/api/auth/social/google/callback
http://localhost:3301/api/auth/social/microsoft/callback
http://localhost:3301/api/auth/social/facebook/callback
```

| Provider | Values | File (`<infra>/stacks/core/env/.env.auth`) | Where to create it |
|---|---|---|---|
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | same | Google Cloud Console -> APIs & Services -> Credentials -> OAuth client ID (Web application) |
| Microsoft | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID` | same (these three keys are not in the file yet - add them) | Entra ID -> App registrations -> New registration. Use a specific tenant id or `consumers` if you want email-based account linking; `common` intentionally does **not** auto-link by email. |
| Facebook | `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | same (add them) | developers.facebook.com -> Create app -> Facebook Login |

After adding credentials: recreate `auth-service`, then as super admin turn each provider on in IAM: `auth.social.enabled=true` **and** `auth.social.<provider>=true` (`PUT /api/iam/settings/<key>`). Details: `ENVIRONMENT.md` section 5.

## D. Real email (skip locally)

| Value | File | Notes |
|---|---|---|
| `EMAIL_USER`, `EMAIL_PASS` (and `EMAIL_HOST`/`EMAIL_PORT`) | `<infra>/stacks/utility/env/.env.app` | Locally leave empty and keep `EMAIL_HOST=mailpit` so mail is caught at http://localhost:8025. For real delivery use an SMTP relay or a Gmail app password. |

## E. Storage (skip locally)

`STORAGE_TYPE=local` needs nothing. For cloud storage fill the matching block in `<infra>/stacks/utility/env/.env.file-upload`: `R2_*` (Cloudflare R2), `AZURE_CONNECTION_STRING` + `AZURE_CONTAINER`, or `S3_*` / `GCS_*`.

## F. Anti-abuse (optional)

`TURNSTILE_SECRET_KEY` in `.env.auth` (Cloudflare Turnstile) turns on CAPTCHA at sign-up/login. Leave unset to keep it off.

---

## What is already set for you

All of these are filled and consistent (verified by `scripts/preflight_env.py`, 0 FAIL): JWT, cookie, SSO and encryption secrets; the RS256 key pair; IAM bootstrap admin (explicit dev defaults: `super-admin@example.com` and the dev password from IAM's seed, identical in the gateway's `IAM_ADMIN_*`); the shared upload secret across RAG and the upload service; the notification API key across IAM and notification; CORS origins; all local service URLs (`host.docker.internal:3301`, `:4005`, `mailpit:1025`); `AUTH_REQUIRED=true`, `VECTOR_STORE_BACKEND=pgvector`, `ADMIN_ROLES`, `UPLOAD_SERVICE_ROLE`, and the frontend URLs.

Two things are placeholders on purpose: RAG `IAM_CLIENT_ID` / `IAM_CLIENT_SECRET` are only read by a service-token flow nothing uses yet.

**Before production** change the dev bootstrap password and generate fresh secrets; the local defaults are for development only.
