#!/bin/sh
# Restores a Postgres dump produced by scripts/backup_db.sh. Destructive: drops and recreates
# every object in the target database's public schema before restoring, per pg_restore --clean
# --if-exists. Requires explicit confirmation unless -y/--yes is passed.
#
# Usage:
#   scripts/restore_db.sh storage/backups/my_database_name_20260930T120000Z.dump
#   scripts/restore_db.sh --yes storage/backups/my_database_name_20260930T120000Z.dump
set -eu

cd "$(dirname "$0")/.."

CONFIRM=0
if [ "${1:-}" = "-y" ] || [ "${1:-}" = "--yes" ]; then
  CONFIRM=1
  shift
fi

DUMP_FILE="${1:-}"
if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
  echo "Usage: $0 [-y|--yes] <dump-file>" >&2
  echo "  (dump files are written by scripts/backup_db.sh into storage/backups/)" >&2
  exit 1
fi

if [ -f .env ]; then
  POSTGRES_USER=$(grep -E '^POSTGRES_USER=' .env | tail -n1 | cut -d= -f2-)
  POSTGRES_DB=$(grep -E '^POSTGRES_DB=' .env | tail -n1 | cut -d= -f2-)
fi
POSTGRES_USER="${POSTGRES_USER:-my_db_user}"
POSTGRES_DB="${POSTGRES_DB:-my_database_name}"

if [ "$CONFIRM" -ne 1 ]; then
  echo "This will DROP AND REPLACE every object in '$POSTGRES_DB' with the contents of:"
  echo "  $DUMP_FILE"
  printf "Type the database name (%s) to confirm: " "$POSTGRES_DB"
  read -r ANSWER
  if [ "$ANSWER" != "$POSTGRES_DB" ]; then
    echo "Confirmation did not match. Aborting, nothing was touched." >&2
    exit 1
  fi
fi

echo "Restoring '$POSTGRES_DB' (as $POSTGRES_USER) from $DUMP_FILE ..."
docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$DUMP_FILE"
echo "Restore complete."
