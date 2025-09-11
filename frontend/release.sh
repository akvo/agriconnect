#!/usr/bin/env bash
#shellcheck disable=SC2039

set -euo pipefail

yarn install --no-progress --frozen-lock
yarn build
yarn eslint
yarn prettier --check src/
yarn test --passWithNoTests
