#!/bin/sh
# Builds and tags the image docker-compose.prod.yml expects (easydev/ai-platform:${VERSION}) --
# docs/BUGS.md item 7: docker-compose.prod.yml requires a pre-built, already-tagged image via
# Compose's `${VERSION:?...}` syntax (deliberately no floating `latest`, so a redeploy's image is
# always answerable and rollback is just re-running with an older VERSION), but nothing in the
# repo actually built one — `docker compose -f docker-compose.prod.yml up` failed immediately
# with an image-not-found error.
#
# Usage:
#   scripts/build_prod_image.sh 1.4.2                 # build and tag locally only
#   PUSH=1 scripts/build_prod_image.sh 1.4.2           # also push to the configured registry
#
# api and worker (docker/Dockerfile, docker/Dockerfile.worker) already build from the SAME
# dependency set (see docker/Dockerfile.worker's own comment), but docker-compose.prod.yml
# references one image for both services — this builds docker/Dockerfile once and tags it for
# both, matching what the compose file already expects. If api/worker ever need to genuinely
# diverge (different base image, different extra deps), this script and the compose file's
# `image:` lines both need to build/reference two tags instead of one.
set -eu

cd "$(dirname "$0")/.."

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version>  (e.g. $0 1.4.2)" >&2
  echo "  Tags the image as easydev/ai-platform:<version>, matching what" >&2
  echo "  docker-compose.prod.yml's VERSION build-arg expects." >&2
  exit 1
fi

IMAGE="easydev/ai-platform:${VERSION}"

echo "Building $IMAGE from docker/Dockerfile ..."
docker build -t "$IMAGE" -f docker/Dockerfile .

echo "Build complete: $IMAGE"

if [ -n "${PUSH:-}" ]; then
  echo "Pushing $IMAGE ..."
  docker push "$IMAGE"
fi

echo
echo "Deploy with:"
echo "  VERSION=$VERSION docker compose -f docker-compose.prod.yml up -d"
