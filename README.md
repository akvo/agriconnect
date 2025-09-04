# AgriConnect

[![Test](https://github.com/akvo/agriconnect/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/akvo/agriconnect/actions/workflows/test.yml)
[![Coverage Status](https://coveralls.io/repos/github/akvo/agriconnect/badge.svg?branch=main)](https://coveralls.io/github/akvo/agriconnect?branch=main)
[![GitHub repo size](https://img.shields.io/github/repo-size/akvo/agriconnect)](https://github.com/akvo/agriconnect)
[![GitHub top language](https://img.shields.io/github/languages/top/akvo/agriconnect)](https://github.com/akvo/agriconnect)
[![GitHub issues](https://img.shields.io/github/issues/akvo/agriconnect)](https://github.com/akvo/agriconnect/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/akvo/agriconnect)](https://github.com/akvo/agriconnect/commits/main)

## Development Setup

1. Create the Docker sync volume:
```bash
docker volume create agriconnect-docker-sync
```

2. Start the development environment:
```bash
./dc.sh up -d
```

That's it! Your development environment should now be running.