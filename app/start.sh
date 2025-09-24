#!/bin/sh

echo "AGRICONNECT_SERVER_URL=${BACKEND_IP_ADDRESS}" >.env

yarn install
yarn start
