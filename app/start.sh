#!/bin/sh

echo "EXPO_PUBLIC_AGRICONNECT_SERVER_URL=${BACKEND_IP_ADDRESS}" >.env

yarn install
yarn start
