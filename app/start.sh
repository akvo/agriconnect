#!/bin/sh

echo "SERVER_URL=${BACKEND_IP_ADDRESS}" >.env

tail -f /dev/null

yarn install
yarn start
