#!/bin/sh
set -e

# Celery entrypoint script for AgriConnect
# Usage: ./entrypoint-celery.sh <worker|beat>

CELERY_MODE=${1:-worker}

echo "⏳ Waiting for PostgreSQL..."
while ! nc -z db 5432; do
    sleep 1
done
echo "✅ PostgreSQL started"

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
