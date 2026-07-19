#!/bin/sh

set -e

echo "Starting Worker..."

exec python -m packages.worker.main