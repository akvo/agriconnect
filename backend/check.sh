#!/usr/bin/env bash

set -euo pipefail

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
