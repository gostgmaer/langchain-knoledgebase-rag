#!/bin/sh
# Loads the production secrets file (docker-compose.prod.yml's `secrets: app_env` —
# docs/DEPLOYMENT.md §8) into real environment variables before running the actual command, so the
# app itself needs zero changes: packages/config/*.py (pydantic-settings) already reads plain env
# vars, same as it always has for a local .env — this just gets the sensitive subset there from a
# file Docker mounts at /run/secrets/app_env instead of the generic `env_file: .env` (which
# production's own .env should NOT contain these keys at all — see secrets/app.env.example).
#
# One file, not one Docker secret per key: Compose's secrets mechanism only cares that each secret
# is a file mounted under /run/secrets/ — nothing requires a 1:1 split. secrets/app.env is an
# ordinary KEY=value file (same shape as .env).
#
# Parsed line-by-line with `read`, NOT sourced with `.`/`source` — sourcing runs each line as a
# shell assignment, so a value containing `$` would be (mis)parsed as a variable reference, and a
# value containing backticks or `$(...)` would execute arbitrary commands. `read` treats each line
# as inert text, so a secret value can contain any character without special-casing it.
set -eu

secrets_file=/run/secrets/app_env
if [ -f "$secrets_file" ]; then
    # POSIX sh has no $'\r' — carry a literal CR in a variable to strip CRLF line endings from
    # editor-saved files; Docker's own secret files never add one, so this is a safety net.
    cr=$(printf '\r')
    while IFS= read -r line || [ -n "$line" ]; do
        line=${line%"$cr"}
        case "$line" in
            ''|'#'*) continue ;;
        esac
        key=${line%%=*}
        value=${line#*=}
        export "$key=$value"
    done < "$secrets_file"
fi

exec "$@"
