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

- **Monitor Celery worker:**
  ```bash
  ./dc.sh logs celery-worker -f  # Follow Celery worker logs
  ./dc.sh restart celery-worker   # Restart worker after code changes
  ```

### Database Management

- **Reset customer onboarding:**
  ```bash
  ./dc.sh exec backend python -m seeder.reset_onboarding --phone-number="+25512345xxxx"
  ```

  **⚠️ WARNING**: This script will permanently delete:
  - Customer's full name
  - Language preference
  - All profile data (age group, gender, crop types, etc.)
  - Onboarding attempts counter
  - Administrative area assignments (ward/region associations)
  - Onboarding status (resets to `not_started`)

  **Use Cases**:
  - Testing onboarding flow with real phone numbers
  - Allowing customers to re-register with updated information
  - Fixing corrupted onboarding data

  **Important Notes**:
  - The phone number itself is NOT deleted (customer account remains)
  - Customer's message history is preserved
  - This action cannot be undone
  - Always confirm the phone number before executing

### Available Services

The environment includes the following services:

- **db**: PostgreSQL database (port 5432)
- **redis**: Redis server for Celery task queue (port 6379)
- **backend**: Python FastAPI backend (port 8000)
- **celery-worker**: Celery worker for asynchronous tasks (broadcast messages, retries)
- **frontend**: Node.js frontend application (port 3000)
- **mobileapp**: React Native mobile app development (port 8081)
- **pgadmin**: Database management interface (port 5050)
- **mainnetwork**: Network service with port mappings

### Access URLs

Once the environment is running, you can access:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs (Swagger UI)
- pgAdmin: http://localhost:5050
- Mobile app development via [Expo GO](https://play.google.com/store/apps/details?id=host.exp.exponent&hl=en): exp://<your_ip_address>:19000

## Features

### Broadcast Messaging System

AgriConnect includes a comprehensive broadcast messaging system for sending WhatsApp messages to groups of farmers:

- **Group Management**: Create and manage broadcast groups with filters (administrative area, age group, crop type)
- **Message Broadcasting**: Send messages to multiple recipients via WhatsApp
- **Asynchronous Processing**: Uses Celery for background task processing
- **Delivery Tracking**: Real-time status tracking (pending → queued → processing → completed)
- **Automatic Retries**: Failed messages are automatically retried with configurable intervals
- **Two-Step Delivery**: WhatsApp template message followed by actual message content
- **Mobile Integration**: View and manage broadcast messages from the mobile app

#### Celery Task Queue

The broadcast system uses **Celery** with **Redis** for asynchronous task processing:

- **Tasks**:
  - `process_broadcast`: Processes broadcast messages and sends to recipients
  - `send_actual_message`: Sends the actual message after template confirmation
  - `retry_failed_broadcasts`: Periodic task to retry failed message deliveries

- **Configuration**:
  - Broadcast batch size: Configure via `BROADCAST_BATCH_SIZE` environment variable (default: 50)
  - Retry intervals: Configure via `BROADCAST_RETRY_INTERVALS` environment variable (default: 5,15,60 minutes)
  - WhatsApp templates: Configure via environment variables (see `.env.example`)

- **Monitoring**:
  ```bash
  # View Celery worker logs
  ./dc.sh logs celery-worker -f

  # Check Redis connection
  ./dc.sh exec redis redis-cli ping

  # Monitor task execution
  ./dc.sh logs celery-worker | grep "Task.*succeeded"
  ```

- **Testing**:
  ```bash
  # Run broadcast tests (mocked to prevent real WhatsApp sends)
  ./dc.sh exec backend pytest tests/test_broadcast_*.py -v

  # TESTING mode automatically prevents real API calls during tests
  # Set TESTING=1 environment variable for development testing
  ```

## Environment Configuration

Create a `.env` file based on `.env.example` with the following key variables:

**Required for Broadcast Messaging:**
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` - Twilio WhatsApp credentials
- `WHATSAPP_BROADCAST_TEMPLATE_SID` - WhatsApp template for broadcast messages
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` - Redis configuration for Celery (auto-configured in Docker)

**Optional Broadcast Configuration:**
- `BROADCAST_BATCH_SIZE` - Recipients per batch (default: 50)
- `BROADCAST_RETRY_INTERVALS` - Retry intervals in minutes (default: 5,15,60)

See `.env.example` for complete configuration options.

## Documentation

Additional documentation is available in the `docs/` directory:

- **[Broadcast API Core Implementation](docs/BROADCAST_API_CORE_IMPLEMENTATION.md)**: Broadcast messaging system architecture and implementation guide
- **[Broadcast API Twilio Integration](docs/BROADCAST_API_TWILIO_INTEGRATION.md)**: Twilio WhatsApp integration and Celery task queue setup
- **[Deployment Pipeline](docs/DEPLOYMENT_PIPELINE.md)**: CI/CD pipeline architecture, Kubernetes deployment, and troubleshooting guide
- **[Mobile App Deployment](docs/MOBILE_APP_DEPLOYMENT.md)**: Complete guide for building and deploying the mobile app using EAS Build and GitHub Actions
- **[Push Notifications](docs/PUSH_NOTIFICATIONS.md)**: Push notification setup, architecture, and troubleshooting guide for mobile app
- **[Mobile Build Quick Reference](docs/MOBILE_BUILD_QUICK_REFERENCE.md)**: Quick commands and troubleshooting for mobile app builds
- **[Storage System](docs/STORAGE_SYSTEM.md)**: File upload and storage system configuration and usage guide
- **[CLAUDE.md](CLAUDE.md)**: Project architecture and development guidelines for Claude Code
