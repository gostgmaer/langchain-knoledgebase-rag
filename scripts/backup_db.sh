#!/bin/sh
# Backs up the Postgres database (app data + pgvector embeddings, when pgvector is the vector
# store backend) to a compressed, restorable dump. docs/BUGS.md item 3: no backup/restore
# strategy existed at all before this script.
#
# Usage:
#   scripts/backup_db.sh                  # dump the running `postgres` compose service
#   RETENTION_DAYS=7 scripts/backup_db.sh # also prune dumps older than 7 days (default: keep all)
#
# Reads POSTGRES_USER/POSTGRES_DB from .env (falling back to the docker-compose.yml defaults) and
# runs pg_dump *inside* the postgres container via `docker compose exec`, so it works identically
# whether this is run on the host or in CI, without needing a local psql/pg_dump install matching
# the server's major version.
set -eu

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  # Only the two vars this script needs, not a full `source .env` (which would also export every
  # API key in it into this shell for no reason).
  POSTGRES_USER=$(grep -E '^POSTGRES_USER=' .env | tail -n1 | cut -d= -f2-)
  POSTGRES_DB=$(grep -E '^POSTGRES_DB=' .env | tail -n1 | cut -d= -f2-)
fi
POSTGRES_USER="${POSTGRES_USER:-my_db_user}"
POSTGRES_DB="${POSTGRES_DB:-my_database_name}"

OUT_DIR="storage/backups"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%dT%H%M%SZ)
OUT_FILE="$OUT_DIR/${POSTGRES_DB}_${STAMP}.dump"

echo "Backing up '$POSTGRES_DB' (as $POSTGRES_USER) -> $OUT_FILE"

# Custom format (-Fc): compressed, and restorable selectively (single table, --clean, parallel
# jobs) via pg_restore -- unlike a plain SQL dump, which can only be replayed whole via psql.
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$OUT_FILE"

SIZE=$(du -h "$OUT_FILE" | cut -f1)
echo "Backup complete: $OUT_FILE ($SIZE)"

if [ -n "${RETENTION_DAYS:-}" ]; then
  echo "Pruning dumps older than $RETENTION_DAYS day(s) in $OUT_DIR..."
  find "$OUT_DIR" -name "${POSTGRES_DB}_*.dump" -mtime +"$RETENTION_DAYS" -print -delete
fi
