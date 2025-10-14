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

## Usage

The `./dc.sh` script is a wrapper around Docker Compose that combines multiple compose files for the full development environment. It supports all standard Docker Compose commands:

### Common Commands

- **Start the development environment:**
  ```bash
  ./dc.sh up -d
  ```

- **Stop the development environment:**
  ```bash
  ./dc.sh down
  ```

- **View running services:**
  ```bash
  ./dc.sh ps
  ```

- **View logs:**
  ```bash
  ./dc.sh logs
  ./dc.sh logs -f  # Follow logs
  ./dc.sh logs backend  # View specific service logs
  ```

### Development Commands

- **Execute commands in the backend container:**
  ```bash
  ./dc.sh exec backend <command>
  ```

  Examples:
  ```bash
  ./dc.sh exec backend tests     # Run backend tests
  ./dc.sh exec backend flake8    # Run backend linter
  ./dc.sh exec backend bash      # Open bash shell
  ```

- **Execute commands in the frontend container:**
  ```bash
  ./dc.sh exec frontend <command>
  ```

  Examples:
  ```bash
  ./dc.sh exec frontend prettier --write .  # Format frontend code
  ./dc.sh exec frontend bash                # Open bash shell
  ```

### Available Services

The environment includes the following services:

- **db**: PostgreSQL database (port 5432)
- **backend**: Python FastAPI backend (port 8000)
- **frontend**: Node.js frontend application (port 3000)
- **mobileapp**: React Native mobile app development (port 8081)
- **pgadmin**: Database management interface (port 5050)
- **mainnetwork**: Network service with port mappings

### Access URLs

Once the environment is running, you can access:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- pgAdmin: http://localhost:5050
- Mobile app development via [Expo GO](https://play.google.com/store/apps/details?id=host.exp.exponent&hl=en): exp://<your_ip_address>:14000

## Documentation

Additional documentation is available in the `docs/` directory:

- **[Deployment Pipeline](docs/DEPLOYMENT_PIPELINE.md)**: CI/CD pipeline architecture, Kubernetes deployment, and troubleshooting guide
- **[Mobile App Deployment](docs/MOBILE_APP_DEPLOYMENT.md)**: Complete guide for building and deploying the mobile app using EAS Build and GitHub Actions
- **[Mobile Build Quick Reference](docs/MOBILE_BUILD_QUICK_REFERENCE.md)**: Quick commands and troubleshooting for mobile app builds
- **[Storage System](docs/STORAGE_SYSTEM.md)**: File upload and storage system configuration and usage guide
- **[CLAUDE.md](CLAUDE.md)**: Project architecture and development guidelines for Claude Code
