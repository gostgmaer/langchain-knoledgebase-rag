# Empty file
#!/bin/sh

set -e

echo "Running migrations..."

uv run alembic upgrade head

echo "Migration complete."