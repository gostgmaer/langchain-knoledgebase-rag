# Docker secrets

`docs/DEPLOYMENT.md` §8, `docs/BUGS.md` item 26 — the production deploy path's real secrets
mechanism, instead of the genuinely sensitive values (API keys, passwords, connection strings)
sitting in plain-text in `.env` alongside ordinary config.

## How it works

Each file here is one secret's **raw value**, nothing else — not a `KEY=value` line like `.env`
uses, just the literal value (e.g. `openai_api_key.txt` contains exactly `sk-...`, no quotes, no
trailing `KEY=`). `docker-compose.prod.yml`'s top-level `secrets:` block maps each file to a name;
the services that need it mount it at `/run/secrets/<name>` inside the container.
`scripts/docker_secrets_entrypoint.sh` (wired in as each service's `entrypoint:`) reads every file
under `/run/secrets/`, exports it as an environment variable named after the file (uppercased —
`openai_api_key` → `OPENAI_API_KEY`), then runs the service's real command — the application code
itself needs zero changes, since `packages/config/*.py` already just reads plain environment
variables, exactly as it does today from `.env`.

## Setting this up for a real deploy

1. For each `*.txt.example` file here, create the real `*.txt` file (same name, minus
   `.example`) with the real value — `secrets/openai_api_key.txt`, `secrets/database_url.txt`,
   etc. These are gitignored (`secrets/*.txt` in `.gitignore`) — never commit a real one.
2. `postgres_password.txt` must match whatever `POSTGRES_PASSWORD` the `postgres` service was
   actually initialized with (first boot only — changing it later doesn't change an existing data
   volume, same caveat `.env.example`'s own `POSTGRES_PASSWORD` comment already has).
3. `database_url.txt` should point at the restricted `rag_app` role once `docs/DEPLOYMENT.md` §4's
   RLS setup is in place, not the owner/superuser — `migration_database_url.txt` is the owner
   connection the `migrate` service itself needs for schema DDL and creating that role.
4. Production's real `.env` should **omit** every key listed below entirely — if both `.env` and a
   secret file set the same variable, the secret file wins (the entrypoint script's `export` runs
   after `env_file` is already loaded into the container's environment), but leaving it out of
   `.env` for real avoids the confusion of two sources of truth for one value.

## What's covered

Database/cache: `database_url`, `migration_database_url`, `postgres_password`, `app_db_password`,
`redis_url`.

Auth/crypto: `jwt_secret`, `iam_client_secret`, `iam_introspection_api_key`,
`file_upload_hmac_secret`, `connector_credential_keys` (the Fernet key(s) protecting every stored
connector credential — arguably the single most sensitive value in this whole list),
`connector_render_token`.

LLM providers: `google_api_key`, `openai_api_key`, `anthropic_api_key`, `groq_api_key`.

Tool/integration keys: `serper_api_key`, `tavily_api_key`, `openweather_api_key`,
`newsapi_api_key`, `upload_service_api_key`, `langchain_api_key`.

Not covered, deliberately: plain endpoints/URLs with no embedded credential
(`IAM_BASE_URL`, `UPLOAD_SERVICE_URL`, `OPENWEATHER_BASE_URL`, `NEWSAPI_BASE_URL`,
`CONNECTOR_RENDER_URL`) and ordinary non-sensitive config (timeouts, feature flags, model names) —
those stay in `.env` via `env_file`, same as always.
