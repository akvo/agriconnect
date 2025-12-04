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
- **Modular routers**: `auth.py`, `customers.py`, `admin_users.py`, `knowledge_base.py`, `document.py`,`whatsapp.py`, `devices.py`, `ws.py`
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
- **External AI service integration** - service-agnostic, database-driven configuration
- **Service token management** for external AI services (stored in `service_tokens` table)
- **Webhook callbacks** for real-time updates (AI/KB callbacks do not require authentication)
- **WebSocket (Socket.IO)** for real-time chat communication
- **Push notifications** via Expo Push Notification service
- **Device registration** associated with administrative areas (wards)

### External AI Service Integration

AgriConnect uses a **service-agnostic AI integration** managed via the `service_tokens` database table.

**Configuration:**
- Admin users configure AI services via `/api/admin/service-tokens` API
- Multiple services can be configured, only one active at a time
- Supports any AI service (Akvo RAG, OpenAI, Claude API, etc.)
- Service configuration stored in database, not environment variables
- TTL cache (5 minutes) for optimal performance

**API Endpoints:**
- `POST /api/admin/service-tokens` - Create new service token
- `GET /api/admin/service-tokens` - List all service tokens
- `PUT /api/admin/service-tokens/{id}` - Update service token
- `DELETE /api/admin/service-tokens/{id}` - Delete service token

**Environment Variables:**
- No external AI environment variables required
- All configuration managed via database (`service_tokens` table)

**Token Management:**
- Access tokens and service URLs stored in `service_tokens` table
- Managed via admin API (no environment variables for tokens)
- Cache invalidation on token updates ensures immediate effect
- Multiple services supported, switch via `active` flag

**Database Schema:**
```sql
CREATE TABLE service_tokens (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR NOT NULL UNIQUE,
    access_token VARCHAR,            -- Token to authenticate with external service
    chat_url VARCHAR,                -- URL for chat job requests
    upload_url VARCHAR,              -- URL for Document upload job requests
    kb_url VARCHAR,                  -- URL for CRUD a Knowledge Base
    document_url VARCHAR,            -- URL for update, view, delete a Document
    default_prompt VARCHAR,          -- Default system prompt for AI service
    active INTEGER DEFAULT 0,        -- 0=inactive, 1=active (only one can be active)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Authentication Flow with External AI Services

- **AgriConnect → External AI**: Uses service tokens (from `service_tokens` table)
- **External AI → AgriConnect**: No authentication required for callback endpoints (`/api/callback/ai`, `/api/callback/kb`)
- Service tokens manage **outbound authentication only**
- Simplified token management by eliminating bidirectional authentication

### OpenAI Service Integration

AgriConnect includes a **direct OpenAI API integration** for features that require synchronous responses and don't involve external RAG/knowledge base services.

**Use Cases:**
- **Speech-to-text transcription** - Convert voice messages to text
- **Onboarding workflows** - Personalized farmer onboarding
- **Content moderation** - Check messages for policy violations
- **Structured data extraction** - Extract information from queries
- **Text embeddings** - Semantic search and similarity

**Configuration:**
- API key stored in `.env` file (`OPENAI_API_KEY`)
- Settings managed via `config.json` (models, parameters, feature flags)
- Feature-specific configurations (transcription, onboarding, moderation)

**Service Methods:**
- `chat_completion()` - Generate chat responses
- `chat_completion_stream()` - Streaming chat responses
- `transcribe_audio()` - Convert voice/audio to text (speech-to-text)
- `moderate_content()` - Check content for policy violations
- `create_embedding()` - Generate text embeddings
- `structured_output()` - Get JSON-structured responses

**Example Usage:**
```python
from services.openai_service import get_openai_service

# Convert voice message to text (speech-to-text)
service = get_openai_service()
transcription = await service.transcribe_audio(
    audio_url="https://example.com/voice.mp3"
)
# transcription.text contains the text version of the audio

# Generate onboarding message
response = await service.chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful agricultural assistant..."},
        {"role": "user", "content": "How do I get started?"}
    ]
)

# Moderate content
moderation = await service.moderate_content("User message text")
if moderation.flagged:
    # Handle inappropriate content
    pass
```

**Key Differences from External AI Service:**
- **Synchronous**: Immediate response (not job-based with callbacks)
- **Direct API**: OpenAI API calls (not external RAG service)
- **Configuration**: Environment variable + config.json (not database)
- **Use Cases**: Speech-to-text, moderation, general AI tasks (not KB-based chat or WHISPER suggestions)

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
