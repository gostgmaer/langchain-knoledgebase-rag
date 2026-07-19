# Empty file
#!/bin/sh
set -e

echo "Starting AI Platform..."

exec uvicorn packages.api.app:app \
    --host 0.0.0.0 \
    --port 8000