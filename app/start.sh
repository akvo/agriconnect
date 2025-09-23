#!/bin/sh

echo "SERVER_URL=${BACKEND_IP_ADDRESS}" >.env

yarn install

tail -f /dev/null

yarn start
