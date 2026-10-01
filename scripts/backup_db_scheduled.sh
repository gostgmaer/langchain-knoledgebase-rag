#!/bin/sh
# Runs inside docker-compose.prod.yml's `backup` sidecar — same `pg_dump -Fc` convention as
# scripts/backup_db.sh (docs/BUGS.md item 3: "no backup/restore strategy ... nothing schedules
# this automatically"), looped on a real interval instead of being a manual, unscheduled step.
#
# The sidecar's own image is pgvector/pgvector:pg17 (same image `postgres` runs), so its bundled
# pg_dump always matches the server's major version exactly — the same reason scripts/backup_db.sh
# runs pg_dump *inside* the postgres container via `docker compose exec` rather than needing a
# host-installed client. A sidecar can't do that (no docker socket mount, deliberately — handing a
# backup container access to the docker socket is a real privilege-escalation surface for what
# should be a narrowly-scoped job), so this connects directly over the compose network instead
# (PGHOST=postgres), which is exactly as safe: pg_dump is read-only against the database.
set -eu

INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
OUT_DIR="/backups"
PGHOST="${PGHOST:-postgres}"

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "[$(date -u +%FT%TZ)] Scheduled backup sidecar starting — every ${INTERVAL_SECONDS}s, keeping ${RETENTION_DAYS} day(s), writing to $OUT_DIR"

while true; do
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  OUT_FILE="$OUT_DIR/${POSTGRES_DB}_${STAMP}.dump"

  echo "[$(date -u +%FT%TZ)] Backing up '$POSTGRES_DB' (as $POSTGRES_USER) -> $OUT_FILE"

  if pg_dump -h "$PGHOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc >"$OUT_FILE"; then
    SIZE=$(du -h "$OUT_FILE" | cut -f1)
    echo "[$(date -u +%FT%TZ)] Backup complete: $OUT_FILE ($SIZE)"
    find "$OUT_DIR" -name "${POSTGRES_DB}_*.dump" -mtime +"$RETENTION_DAYS" -print -delete
  else
    echo "[$(date -u +%FT%TZ)] Backup FAILED for this cycle — removing the partial file, previous dumps are untouched" >&2
    rm -f "$OUT_FILE"
  fi

  sleep "$INTERVAL_SECONDS"
done
