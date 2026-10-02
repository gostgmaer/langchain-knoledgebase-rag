#!/bin/sh
# Zero-downtime deploy for `api` (docs/BUGS.md item 9) — the real mechanism behind
# docker-compose.prod.yml's api_blue/api_green/traefik services.
#
# Plain `docker compose up -d` on a changed image stops the old `api` container before the new
# one is ready to serve, so there's always a real gap where nothing answers the host port. This
# script avoids that: it starts the *idle* color (whichever of api_blue/api_green isn't currently
# running) on the new version, waits for its own Docker HEALTHCHECK to report healthy — during
# which Traefik is routing to both the old and new containers at once, since they're both real
# backends for the same Traefik service name — and only then stops the old color. If the new
# color never goes healthy, it's torn down instead and the old color is left running untouched:
# a real rollback-on-failure, not just a deploy that might leave things broken.
#
# Usage:
#   VERSION=1.4.3 scripts/deploy_blue_green.sh
#   HEALTH_TIMEOUT_SECONDS=180 VERSION=1.4.3 scripts/deploy_blue_green.sh   # slower cold start
#
# First-ever deploy (neither color running yet): starts api_blue, same as any other deploy —
# there's just no old color to drain afterward.
set -eu

cd "$(dirname "$0")/.."

: "${VERSION:?Set VERSION to a real image tag before deploying — no floating \"latest\" in production}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-120}"

COMPOSE_FILE="docker-compose.prod.yml"

running_services() {
    VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null
}

if running_services | grep -qx api_blue; then
    ACTIVE=api_blue
    TARGET=api_green
elif running_services | grep -qx api_green; then
    ACTIVE=api_green
    TARGET=api_blue
else
    ACTIVE=""
    TARGET=api_blue
fi

echo "Active: ${ACTIVE:-none (first deploy)}. Deploying $VERSION to $TARGET..."

# Re-run migrate every time, same as a plain `up -d` would via its own depends_on — picks up any
# new migration/role changes before the new color starts, not just on the very first deploy.
VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" up -d migrate
VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" up -d "$TARGET"

echo "Waiting up to ${HEALTH_TIMEOUT_SECONDS}s for $TARGET to report healthy..."
elapsed=0
while true; do
    container_id=$(VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" ps -q "$TARGET")
    status=$(docker inspect -f '{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "unknown")

    if [ "$status" = "healthy" ]; then
        echo "$TARGET is healthy."
        break
    fi

    if [ "$elapsed" -ge "$HEALTH_TIMEOUT_SECONDS" ]; then
        echo "$TARGET did not become healthy within ${HEALTH_TIMEOUT_SECONDS}s (last status: $status)." >&2
        echo "Rolling back: stopping $TARGET. ${ACTIVE:+$ACTIVE is untouched and still serving.}" >&2
        VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" stop "$TARGET"
        VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" rm -f "$TARGET"
        exit 1
    fi

    sleep 2
    elapsed=$((elapsed + 2))
done

if [ -n "$ACTIVE" ]; then
    echo "Draining and stopping $ACTIVE..."
    VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" stop "$ACTIVE"
    VERSION="$VERSION" docker compose -f "$COMPOSE_FILE" rm -f "$ACTIVE"
fi

echo "Deploy complete. $TARGET ($VERSION) is now the only running api replica."
