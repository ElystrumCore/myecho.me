#!/bin/sh
set -e
echo "Running alembic migrations..."
alembic upgrade head
echo "Starting uvicorn on port ${PORT:-8006}..."
exec uvicorn echo.main:app --host 0.0.0.0 --port "${PORT:-8006}"
