#!/bin/sh
# Loads Docker Compose secrets (docker-compose.prod.yml's `secrets:` — docs/DEPLOYMENT.md §8) into
# real environment variables before running the actual command, so the app itself needs zero
# changes: packages/config/*.py (pydantic-settings) already reads plain env vars, same as it
# always has for a local .env — this just gets the sensitive subset there from a file instead of
# the generic `env_file: .env` env_file (which production's own .env should NOT contain the
# secret-mounted keys at all — see .env.example's note on each one).
#
# Generic by design, not one `export X=$(cat ...)` line per secret: every file under
# /run/secrets/ becomes an env var named after the file, uppercased (Compose's own
# `secrets: - name` convention already names each file after its real env var, lowercased —
# matching that back is the only naming rule this script assumes). Adding a new secret later
# means adding it to docker-compose.prod.yml's `secrets:` list, not touching this script.
set -eu

if [ -d /run/secrets ]; then
    for secret_file in /run/secrets/*; do
        [ -f "$secret_file" ] || continue
        name=$(basename "$secret_file")
        # Upper-cases via tr (POSIX sh has no ${var^^}) — e.g. openai_api_key -> OPENAI_API_KEY.
        var_name=$(echo "$name" | tr '[:lower:]' '[:upper:]')
        # $() strips a trailing newline, which text-editor-saved secret files commonly have;
        # Docker's own secret files never add one, so this is a safety net, not a real case split.
        value=$(cat "$secret_file")
        export "$var_name=$value"
    done
fi

exec "$@"
