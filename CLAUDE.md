# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Architecture

AgriConnect is a **multi-platform agricultural application** with three main components:

- **Backend**: Python FastAPI REST API with PostgreSQL
- **Frontend**: Next.js 15 web application with React 19 and TypeScript
- **Mobile App**: React Native/Expo application with TypeScript

## Development Environment Setup

### Initial Setup
```bash
docker volume create agriconnect-docker-sync
./dc.sh up -d
```

### Service Access URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs
- **pgAdmin**: http://localhost:5050
- **Mobile App**: exp://<your_ip_address>:14000 (via Expo Go)

## Common Commands

### Environment Management
```bash
./dc.sh up -d           # Start all services
./dc.sh down            # Stop all services
./dc.sh ps               # View running services
./dc.sh logs -f          # Follow all logs
./dc.sh logs backend     # View specific service logs
```

### Backend Development (FastAPI)
```bash
./dc.sh exec backend tests           # Run backend tests
./dc.sh exec backend flake8          # Run backend linter
./dc.sh exec backend bash            # Open backend shell
./dc.sh exec backend python -m pytest tests/ -v  # Run tests with verbose output
```

### Frontend Development (Next.js)
```bash
./dc.sh exec frontend prettier --write .    # Format frontend code
./dc.sh exec frontend bash                  # Open frontend shell
./dc.sh exec frontend yarn dev              # Start development server
./dc.sh exec frontend yarn lint             # Run ESLint
```

### Mobile App Development (Expo)
```bash
./dc.sh exec mobileapp bash                 # Open mobile app shell
./dc.sh exec mobileapp yarn start           # Start Expo development server
./dc.sh exec mobileapp yarn lint            # Run ESLint
```

## Required Environment Variables

Create `.env` file based on `.env.example`:

- **Twilio Integration**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- **Email Service**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_USE_TLS`
- **Web Domain**: `WEBDOMAIN` for email links

## Code Style & Standards

### Python (Backend)
- Follow PEP 8 guidelines
- Use Black formatter with 79 character line limit
- Use flake8 for linting
- Write pytest tests with coverage

### TypeScript (Frontend & Mobile)
- Use ESLint with Next.js/Expo configurations
- Use Prettier for code formatting
- Follow TypeScript strict mode guidelines
- Write Jest tests for frontend components

## Project Structure

### Backend (`/backend/`)
- **FastAPI** framework with SQLAlchemy ORM
- **Alembic** for database migrations
- **JWT authentication** system
- **Modular routers**: `auth.py`, `customers.py`, `admin_users.py`, `knowledge_base.py`, `whatsapp.py`
- **Services layer** for business logic
- **Tests** in `/tests/` directory

### Frontend (`/frontend/`)
- **Next.js 15** with App Router
- **React 19** with TypeScript
- **Tailwind CSS** for styling
- **Axios** for API communication
- **Heroicons** for icons
- **Jest** and **React Testing Library** for testing

### Mobile App (`/app/`)
- **React Native** with Expo Router
- **TypeScript** configuration
- **Expo SDK 54**
- **React Navigation** for routing
- **Expo UI** components and utilities

## Database Management

- **PostgreSQL 17** with automatic initialization
- **Alembic** migrations run on backend startup
- **pgAdmin** available at http://localhost:5050
- Database models in `/backend/models/` directory

## API Architecture

- **REST API** with OpenAPI documentation
- **JWT-based authentication**
- **Twilio WhatsApp integration** for messaging
- **Email notification system**
- **Service token management** for API access
- **Webhook callbacks** for real-time updates

## Development Workflow

1. Always use `./dc.sh exec backend <command>` for backend operations
2. Database migrations run automatically on backend startup
3. Hot reload enabled for all development services
4. Use the appropriate shell for each service when debugging
5. Run tests and linters before committing changes

## Testing

- **Backend**: pytest with coverage reporting
- **Frontend**: Jest with React Testing Library
- **Coverage**: Integrated with Coveralls CI/CD
- **API testing**: Access Swagger docs at http://localhost:8000/api/docs
