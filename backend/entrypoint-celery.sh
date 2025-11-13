#!/bin/sh
set -e

# Celery entrypoint script for AgriConnect
# Usage: ./entrypoint-celery.sh <worker|beat>

CELERY_MODE=${1:-worker}

# Install system dependencies if needed
if ! command -v nc >/dev/null 2>&1; then
    echo "📦 Installing system dependencies..."
    apt-get update && apt-get install -y build-essential netcat-traditional && rm -rf /var/lib/apt/lists/*
fi

# Install Python dependencies if needed
if ! pip show celery >/dev/null 2>&1; then
    echo "📦 Installing Python dependencies..."
    pip install --no-cache-dir -r requirements.txt
fi

echo "⏳ Waiting for PostgreSQL..."
# Extract host and port from DATABASE_URL or use defaults
DB_HOST="db"
DB_PORT="5432"

# Try to parse from DATABASE_URL if available
if [ -n "$DATABASE_URL" ]; then
    # Extract host from DATABASE_URL (handles postgresql://user:pass@host:port/db)
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
fi

# Only wait for DB if not localhost (in K8s, Cloud SQL Proxy starts alongside)
if [ "$DB_HOST" != "localhost" ] && [ "$DB_HOST" != "127.0.0.1" ]; then
    while ! nc -z "$DB_HOST" "$DB_PORT"; do
        sleep 1
    done
    echo "✅ PostgreSQL started"
else
    echo "✅ PostgreSQL (using Cloud SQL Proxy on localhost)"
fi

echo "⏳ Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
    sleep 1
done
echo "✅ Redis started"

if [ "$CELERY_MODE" = "beat" ]; then
    echo "🚀 Starting Celery beat scheduler..."
    celery -A celery_app beat --loglevel=info
else
    echo "🚀 Starting Celery worker..."
    celery -A celery_app worker --loglevel=info --concurrency=2
fi
