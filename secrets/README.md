# Docker secrets

`docs/DEPLOYMENT.md` §8, `docs/BUGS.md` item 26 — the production deploy path's real secrets
mechanism, instead of the genuinely sensitive values (API keys, passwords, connection strings)
sitting in plain-text in `.env` alongside ordinary config.

## How it works

Two files here hold real values:

- **`app.env`** — one `KEY=value` file (same shape as `.env`), covering every secret-managed value
  except the Postgres superuser password. Mounted as a single Docker secret at
  `/run/secrets/app_env`. `scripts/docker_secrets_entrypoint.sh` (wired in as each service's
  `entrypoint:`) sources it directly (`set -a; . /run/secrets/app_env; set +a`) before running the
  service's real command — the application code itself needs zero changes, since
  `packages/config/*.py` already just reads plain environment variables, exactly as it does today
  from `.env`.
- **`postgres_password.txt`** — the Postgres superuser password, as a single raw value (no `KEY=`
  prefix). Kept separate because the official `postgres` image has its own native
  `POSTGRES_PASSWORD_FILE` support, which expects a file containing only the value — it never goes
  through the entrypoint wrapper at all.

One file for everything else, not twenty — Compose's `secrets:` mechanism only requires each secret
be *a* file; nothing requires a 1:1 split per key. A single `KEY=value` file is simpler to set up
(one file to fill in) and simpler to source (no filename→env-var-name convention to maintain).

## Setting this up for a real deploy

1. Copy `app.env.example` to `app.env` and fill in real values. Copy `postgres_password.txt.example`
   to `postgres_password.txt` and fill in the real Postgres superuser password. Both are gitignored
   (`secrets/app.env`, `secrets/postgres_password.txt` in `.gitignore`) — never commit either.
2. `postgres_password.txt` must match whatever `POSTGRES_PASSWORD` the `postgres` service was
   actually initialized with (first boot only — changing it later doesn't change an existing data
   volume, same caveat `.env.example`'s own `POSTGRES_PASSWORD` comment already has). `app.env`'s own
   `POSTGRES_PASSWORD=` line must match it too — that's what the `backup` service reads.
3. `DATABASE_URL` in `app.env` should point at the restricted `rag_app` role once
   `docs/DEPLOYMENT.md` §4's RLS setup is in place, not the owner/superuser —
   `MIGRATION_DATABASE_URL` is the owner connection the `migrate` service itself needs for schema DDL
   and creating that role.
4. Production's real `.env` should **omit** every key listed in `app.env.example` entirely — if both
   `.env` and `app.env` set the same variable, `app.env` wins (the entrypoint script's `export` runs
   after `env_file` is already loaded into the container's environment), but leaving it out of `.env`
   for real avoids the confusion of two sources of truth for one value.

## What's covered

See `app.env.example` for the full, current list with inline comments — database/cache credentials,
auth/crypto secrets (including the Fernet key(s) protecting every stored connector credential —
arguably the single most sensitive value in the file), LLM-provider API keys, and tool/integration
keys.

Not covered, deliberately: plain endpoints/URLs with no embedded credential
(`IAM_BASE_URL`, `UPLOAD_SERVICE_URL`, `OPENWEATHER_BASE_URL`, `NEWSAPI_BASE_URL`,
`CONNECTOR_RENDER_URL`) and ordinary non-sensitive config (timeouts, feature flags, model names) —
those stay in `.env` via `env_file`, same as always.
