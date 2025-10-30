#!/usr/bin/env bash

set -euo pipefail

echo "Waiting for database to be ready..."
# Wait for PostgreSQL to be ready
for i in {1..30}; do
  if psql "${DATABASE_URL}" -c '\q' 2>/dev/null; then
    echo "Database is ready!"
    break
  fi
  echo "Waiting for database... ($i/30)"
  sleep 2
done

echo "Running database migrations"
alembic upgrade head

echo "Running tests"
export TEST=true
COVERAGE_PROCESS_START=./.coveragerc \
  coverage run --parallel-mode --concurrency=thread,gevent --rcfile=./.coveragerc \
  --omit='patches/*' \
  /usr/local/bin/pytest -vvv -rP

echo "Coverage"
coverage combine --rcfile=./.coveragerc
coverage report -m --rcfile=./.coveragerc --omit='patches/*'
coverage xml --rcfile=./.coveragerc --omit='patches/*'

if [[ -n "${COVERALLS_REPO_TOKEN:-}" ]]; then
  cd /app/backend && COVERALLS_SERVICE_NAME=github-actions coveralls
fi

echo "Running flake8"
flake8 --exclude=alembic,patches
