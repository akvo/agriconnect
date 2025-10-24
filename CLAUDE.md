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
./dc.sh exec mobileapp bash                           # Open mobile app shell
./dc.sh exec mobileapp yarn start                     # Start Expo development server
./dc.sh exec mobileapp yarn lint                      # Run ESLint
./dc.sh stop mobileapp && ./dc.sh up -d mobileapp    # Restart with fresh cache
./dc.sh exec mobileapp rm -rf .expo node_modules/.cache  # Clear Metro cache
```

## Required Environment Variables

Create `.env` file based on `.env.example`:

- **Twilio Integration**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- **Email Service**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_USE_TLS`
- **Web Domain**: `WEBDOMAIN` for email links
- **Push Notifications**: `EXPO_TOKEN` for Expo push notification service
- **Firebase**: `GOOGLE_SERVICES_JSON` path to google-services.json for Android FCM configuration

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
- **Modular routers**: `auth.py`, `customers.py`, `admin_users.py`, `knowledge_base.py`, `whatsapp.py`, `devices.py`, `ws.py`
- **Services layer** for business logic (including push notification service)
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
- **SQLite** local database with expo-sqlite
- **DAO pattern** for database operations
- **Firebase Cloud Messaging (FCM)** for push notifications
- **Expo Notifications** for notification handling
- **WebSocket (Socket.IO)** for real-time chat updates

#### Mobile App Database Architecture

The mobile app uses SQLite for local data storage with a carefully designed architecture to prevent race conditions:

**Key Components:**
- **SQLiteProvider**: Manages single database instance (in `app/_layout.tsx`)
- **Database Context**: Hook to access database from SQLiteProvider
- **DAO Manager**: Data Access Object pattern for type-safe operations
- **Migrations**: Automatic schema migrations on app startup

**Important: Database Connection Rules**
1. **NEVER call `openDatabaseSync()` directly** - always use `useDatabase()` hook
2. **Single database instance** - SQLiteProvider creates the only database connection
3. **Pass database to functions** - all utility functions accept `db: SQLiteDatabase` parameter
4. **Use DAO Manager** - create with `new DAOManager(db)` inside components

**Example Usage:**
```typescript
import { useDatabase } from '@/database';
import { DAOManager } from '@/database/dao';

function MyComponent() {
  const db = useDatabase(); // Get database from context
  const dao = useMemo(() => new DAOManager(db), [db]); // Create DAO manager

  // Use DAO for database operations
  const profile = dao.profile.getCurrentProfile();
  const users = dao.user.findAll();
}
```

**Database Files:**
- `/app/database/index.ts` - Migration runner
- `/app/database/context.ts` - Database context hook
- `/app/database/dao/` - DAO implementations
- `/app/database/migrations/` - Schema migrations
- `/app/database/utils/` - Utility functions (reset, health check)

## Database Management

### Backend Database (PostgreSQL)
- **PostgreSQL 17** with automatic initialization
- **Alembic** migrations run on backend startup
- **pgAdmin** available at http://localhost:5050
- Database models in `/backend/models/` directory

### Mobile App Database (SQLite)
- **expo-sqlite** for local storage
- **Single connection** via SQLiteProvider
- **Automatic migrations** on app startup
- **DAO pattern** for type-safe operations
- Database file: `agriconnect.db` in app's document directory

## API Architecture

- **REST API** with OpenAPI documentation
- **JWT-based authentication**
- **Twilio WhatsApp integration** for messaging
- **Email notification system**
- **Service token management** for outbound API access (e.g., calling Akvo RAG)
- **Webhook callbacks** for real-time updates (AI/KB callbacks do not require authentication)
- **WebSocket (Socket.IO)** for real-time chat communication
- **Push notifications** via Expo Push Notification service
- **Device registration** associated with administrative areas (wards)

### Authentication Flow with Akvo RAG
- **AgriConnect → Akvo RAG**: Uses service tokens (stored in `service_tokens` table with `access_token`, `chat_url`, `upload_url` fields)
- **Akvo RAG → AgriConnect**: No authentication required for callback endpoints (`/api/callback/ai`, `/api/callback/kb`)
- Service tokens manage **outbound authentication only** - no incoming authentication tokens are stored
- This simplifies token management by eliminating bidirectional authentication

## Development Workflow

1. Always use `./dc.sh exec backend <command>` for backend operations
2. Database migrations run automatically on backend startup
3. Hot reload enabled for all development services
4. Use the appropriate shell for each service when debugging
5. Run tests and linters before committing changes

### Mobile App Development Notes

**SQLite Best Practices:**
- Use `useDatabase()` hook to get database instance
- Create DAO manager with `useMemo(() => new DAOManager(db), [db])`
- Never open multiple database connections
- All database utility functions require `db` parameter

**Push Notifications Setup:**
- **Firebase Configuration**: Place `google-services.json` in `app/` directory for Android FCM
- **Expo Token**: Set `EXPO_TOKEN` in `.env` file for push notification service
- **Device Registration**: Devices register with administrative areas (wards) on first app launch
- **Notification Context**: Use `NotificationContext` to manage notification state and active tickets
- **Testing**: Use development builds (`./build-android.sh`) to test push notifications (not available in Expo Go)

**Common Issues:**
- **NullPointerException in SQLite**: Caused by multiple concurrent connections. Solution: Always use database from context, never call `openDatabaseSync()` directly
- **Metro cache issues**: Clear cache with `./dc.sh exec mobileapp rm -rf .expo node_modules/.cache`
- **Hot reload not working**: Restart service with `./dc.sh stop mobileapp && ./dc.sh up -d mobileapp`
- **Push notifications not working**: Ensure you're using a development/production build, not Expo Go. Check Firebase configuration and `EXPO_TOKEN` is set

## Testing

- **Backend**: pytest with coverage reporting
- **Frontend**: Jest with React Testing Library
- **Coverage**: Integrated with Coveralls CI/CD
- **API testing**: Access Swagger docs at http://localhost:8000/api/docs
