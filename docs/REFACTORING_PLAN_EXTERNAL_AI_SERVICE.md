# Refactoring Plan: Generic External AI Service Integration

**Date:** 2025-10-30
**Author:** Deden Bangkit
**Status:** Planning
**Objective:** Replace Akvo RAG-specific implementation with a generic, service-agnostic AI integration using the ServiceToken database model

---

## 📊 Current State Analysis

### Files Using `akvo_rag_service`

1. **`backend/main.py`** (lines 23, 37-48)
   - Startup validation for Akvo RAG configuration
   - Checks `AKVO_RAG_APP_ACCESS_TOKEN` and `AKVO_RAG_APP_KNOWLEDGE_BASE_ID`

2. **`backend/routers/whatsapp.py`** (lines 21, 181, 305, 389)
   - Import: `from services.akvo_rag_service import get_akvo_rag_service`
   - Line 181: WHISPER job creation (escalation flow)
   - Line 305: WHISPER job creation (existing ticket flow)
   - Line 389: REPLY job creation (auto-reply flow)

3. **`backend/routers/knowledge_base.py`** (lines 36, 43, 84-86)
   - TODO comments referencing "Akvo RAG service"
   - Line 84-86: Placeholder for sending files to external service

4. **`backend/services/akvo_rag_service.py`**
   - Service implementation
   - Uses environment variables: `AKVO_RAG_APP_ACCESS_TOKEN`, `AKVO_RAG_APP_KNOWLEDGE_BASE_ID`

5. **`backend/config.py`** (lines 51-85)
   - Akvo RAG configuration from environment variables
   - Lines 77-85: Access token and knowledge base ID

6. **Test files:**
   - `backend/tests/test_akvo_rag_service.py`
   - `backend/tests/test_whatsapp_akvo_rag.py`
   - `backend/tests/conftest.py`

### Key Issues

- ❌ **Hardcoded Akvo RAG references** throughout codebase
- ❌ **Environment variables for tokens** (should be in database via `service_tokens` table)
- ❌ **ServiceToken model not being used** for Akvo RAG integration
- ❌ **Not service-agnostic** - cannot easily switch to different AI providers
- ❌ **Redundant environment variables** in `.env`, `.env.example`, `docker-compose.yml`

### Current Environment Variables (Redundant)

These should be **removed** and moved to database:
- `AKVO_RAG_APP_ACCESS_TOKEN` → `service_tokens.access_token`
- `AKVO_RAG_APP_KNOWLEDGE_BASE_ID` → stored elsewhere or not needed

These should **stay** (infrastructure/deployment settings):
- `AKVO_RAG_BASE_URL` - Base URL of AI service
- `AKVO_RAG_APP_NAME` - App identifier
- `AKVO_RAG_APP_DOMAIN` - Domain for callbacks
- `AKVO_RAG_APP_CHAT_CALLBACK` - Chat callback URL
- `AKVO_RAG_APP_UPLOAD_CALLBACK` - Upload callback URL

---

## 🎯 Refactoring Strategy

### Design Principles

1. **Service-Agnostic:** Works with any AI service (Akvo RAG, OpenAI, Claude, etc.)
2. **Database-Driven:** Configuration stored in `service_tokens` table
3. **Backward Compatible:** No breaking changes during migration
4. **Performance:** TTL cache (5 minutes) to avoid repeated DB queries
5. **Extensible:** Easy to add new AI services without code changes

### Architecture Changes

**Before:**
```
whatsapp.py → akvo_rag_service.py → Environment Variables
                                   → Hardcoded Akvo RAG URLs
```

**After:**
```
whatsapp.py → external_ai_service.py → ServiceToken (DB, cached)
                                     → Generic HTTP client
                                     → Works with any AI service
```

---

## 📝 Implementation Plan

### Phase 1: Create Generic Service (No Breaking Changes)

**Goal:** Build new generic service alongside existing one, keep everything working

#### Step 1.1: Create `ExternalAIService` (Generic)

**File:** `backend/services/external_ai_service.py`

**Features:**
- Service-agnostic HTTP client
- Reads configuration from `service_tokens` table
- TTL cache (5 minutes) for active token
- Same API as `AkvoRagService` for easy migration
- Supports both chat and upload jobs

**Key Methods:**
```python
class ExternalAIService:
    def __init__(self, db: Session)
    def is_configured(self) -> bool
    async def create_chat_job(...) -> Optional[Dict[str, Any]]
    async def create_upload_job(...) -> Optional[Dict[str, Any]]

    # Cache management
    @classmethod
    def _get_cached_token(cls, db: Session) -> Optional[ServiceToken]
    @classmethod
    def invalidate_cache(cls)
```

**Caching Strategy:**
- TTL cache: 5 minutes
- Automatic refresh when cache expires
- Manual invalidation via `invalidate_cache()` when admin updates tokens
- Single database query every 5 minutes (negligible load)

**Implementation Details:**

```python
import time
import json
import httpx
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from models.service_token import ServiceToken
from services.service_token_service import ServiceTokenService
from models.message import MessageType

logger = logging.getLogger(__name__)


class ExternalAIService:
    """
    Generic service for integrating with external AI platforms.

    Service-agnostic - works with any AI service (Akvo RAG, OpenAI, Claude, etc.)
    Configuration managed via ServiceToken database model.

    Caching Strategy: TTL cache (5 minutes) for active service token
    """

    _cached_token: Optional[ServiceToken] = None
    _cache_timestamp: float = 0
    _cache_ttl: int = 300  # 5 minutes

    def __init__(self, db: Session):
        self.db = db
        self.token = self._get_cached_token(db)

    @classmethod
    def _get_cached_token(cls, db: Session) -> Optional[ServiceToken]:
        """Get token from cache or refresh if expired"""
        now = time.time()
        if (cls._cached_token is None or
            now - cls._cache_timestamp > cls._cache_ttl):
            cls._cached_token = ServiceTokenService.get_active_token(db)
            cls._cache_timestamp = now
            if cls._cached_token:
                logger.debug(
                    f"[ExternalAIService] Cached active token: "
                    f"{cls._cached_token.service_name}"
                )
        return cls._cached_token

    @classmethod
    def invalidate_cache(cls):
        """Manually invalidate cache (for admin updates)"""
        cls._cached_token = None
        cls._cache_timestamp = 0

    def is_configured(self) -> bool:
        """Check if service is fully configured"""
        is_valid = bool(
            self.token and
            self.token.chat_url and
            self.token.access_token
        )

        if not is_valid:
            missing = []
            if not self.token:
                missing.append("No active service token")
            elif not self.token.chat_url:
                missing.append("chat_url")
            elif not self.token.access_token:
                missing.append("access_token")

            logger.warning(
                f"[ExternalAIService] Missing configuration: "
                f"{', '.join(missing)}"
            )

        return is_valid

    async def create_chat_job(
        self,
        message_id: int,
        message_type: int,
        customer_id: int,
        ticket_id: Optional[int] = None,
        administrative_id: Optional[int] = None,
        chats: Optional[List[Dict[str, str]]] = None,
        trace_id: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a chat job with external AI service.

        Args:
            message_id: ID of the message being processed
            message_type: 1 (REPLY to farmer) or 2 (WHISPER to EO)
            customer_id: Customer ID
            ticket_id: Optional ticket ID
            administrative_id: Ward ID for context
            chats: Chat history for context
            trace_id: Trace ID for debugging
            prompt: Optional custom prompt (from config if not provided)

        Returns:
            Job response with job_id and status, or None if not configured
        """
        if not self.is_configured():
            logger.error(
                "[ExternalAIService] Cannot create chat job - not configured"
            )
            return None

        url = self.token.chat_url

        # Prepare callback params
        callback_params = {
            "message_id": message_id,
            "message_type": message_type,
            "customer_id": customer_id,
        }

        if message_type == MessageType.WHISPER.value:
            if ticket_id:
                callback_params["ticket_id"] = ticket_id
            if administrative_id:
                callback_params["administrative_id"] = administrative_id

        # Get default prompt from config if not provided
        if not prompt:
            from config import settings
            prompt = settings.akvo_rag_default_chat_prompt

        # Prepare job payload
        job_payload = {
            "job": "chat",
            "prompt": prompt,
            "chats": chats or [],
            "callback_params": callback_params
        }

        if trace_id:
            job_payload["trace_id"] = trace_id

        # Prepare form data
        form_data = {
            "payload": json.dumps(job_payload)
        }

        headers = {
            "Authorization": f"Bearer {self.token.access_token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=form_data,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                msg_type_str = "REPLY" \
                    if message_type == MessageType.REPLY.value \
                    else "WHISPER"
                logger.info(
                    f"✓ Created {msg_type_str} job {data.get('job_id')} "
                    f"for message {message_id} "
                    f"(service: {self.token.service_name})"
                )
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"✗ Failed to create chat job: "
                f"HTTP {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"✗ Failed to create chat job: {e}")
            return None

    async def create_upload_job(
        self,
        file_path: str,
        kb_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create an upload job with external AI service.

        Args:
            file_path: Path to file to upload
            kb_id: Knowledge base ID
            metadata: Optional metadata for the upload

        Returns:
            Job response with job_id and status, or None if not configured
        """
        if not self.is_configured() or not self.token.upload_url:
            logger.error(
                "[ExternalAIService] Cannot create upload job - "
                "not configured or upload_url missing"
            )
            return None

        url = self.token.upload_url

        # Prepare callback params
        callback_params = {
            "kb_id": kb_id
        }

        # TODO: Implement file upload logic
        # This depends on how external service expects files

        logger.info(
            f"Upload job creation for KB {kb_id} "
            f"to {self.token.service_name}"
        )
        return None  # Placeholder


def get_external_ai_service(db: Session) -> ExternalAIService:
    """Get ExternalAIService instance"""
    return ExternalAIService(db)
```

#### Step 1.2: Update `config.py` - Remove Redundant Env Vars

**File:** `backend/config.py`

**Changes:**
- **Remove** lines 77-85: `akvo_rag_access_token`, `akvo_rag_knowledge_base_id`
- **Keep** infrastructure settings: `base_url`, `app_name`, `domain`, callbacks

```python
# Settings class (lines 36-139)

# Keep these - infrastructure/deployment settings
akvo_rag_base_url: str = os.getenv(
    "AKVO_RAG_BASE_URL",
    _config.get("akvo_rag", {}).get("base_url"),
)
akvo_rag_app_name: str = os.getenv(
    "AKVO_RAG_APP_NAME",
    _config.get("akvo_rag", {}).get("app_name"),
)
akvo_rag_domain: str = os.getenv(
    "AKVO_RAG_APP_DOMAIN",
    _config.get("akvo_rag", {}).get("domain"),
)
akvo_rag_chat_callback: str = os.getenv(
    "AKVO_RAG_APP_CHAT_CALLBACK",
    _config.get("akvo_rag", {}).get("chat_callback"),
)
akvo_rag_upload_callback: str = os.getenv(
    "AKVO_RAG_APP_UPLOAD_CALLBACK",
    _config.get("akvo_rag", {}).get("upload_callback"),
)
akvo_rag_callback_token: str = _config.get("akvo_rag", {}).get(
    "callback_token"
)
akvo_rag_default_chat_prompt: str = _config.get("akvo_rag", {}).get(
    "default_chat_prompt"
)

# REMOVE THESE - now in database via ServiceToken
# akvo_rag_access_token: Optional[str] = os.getenv(
#     "AKVO_RAG_APP_ACCESS_TOKEN",
#     _config.get("akvo_rag", {}).get("access_token"),
# )
# akvo_rag_knowledge_base_id: Optional[int] = (
#     int(os.getenv("AKVO_RAG_APP_KNOWLEDGE_BASE_ID"))
#     if os.getenv("AKVO_RAG_APP_KNOWLEDGE_BASE_ID")
#     else _config.get("akvo_rag", {}).get("knowledge_base_id")
# )
```

---

### Phase 2: Migration (Backward Compatible)

**Goal:** Replace Akvo RAG service with generic service, no breaking changes

#### Step 2.1: Update `routers/whatsapp.py`

**File:** `backend/routers/whatsapp.py`

**Lines to change:** 21, 181, 305, 389

```python
# Line 21 - Import change
# OLD:
from services.akvo_rag_service import get_akvo_rag_service

# NEW:
from services.external_ai_service import get_external_ai_service

# Line 181 - Escalation WHISPER job
# OLD:
rag_service = get_akvo_rag_service()
asyncio.create_task(
    rag_service.create_chat_job(...)
)

# NEW:
ai_service = get_external_ai_service(db)  # Pass db session
asyncio.create_task(
    ai_service.create_chat_job(...)  # Same API!
)

# Line 305 - Existing ticket WHISPER job
# OLD:
rag_service = get_akvo_rag_service()
asyncio.create_task(
    rag_service.create_chat_job(...)
)

# NEW:
ai_service = get_external_ai_service(db)
asyncio.create_task(
    ai_service.create_chat_job(...)
)

# Line 389 - Auto-reply REPLY job
# OLD:
rag_service = get_akvo_rag_service()
asyncio.create_task(
    rag_service.create_chat_job(...)
)

# NEW:
ai_service = get_external_ai_service(db)
asyncio.create_task(
    ai_service.create_chat_job(...)
)
```

**Note:** The API is identical, so no changes to function parameters needed.

#### Step 2.2: Update `main.py` - Startup Validation

**File:** `backend/main.py`

**Lines to change:** 23, 36-48

```python
# Line 23 - Import change
# OLD:
from services.akvo_rag_service import get_akvo_rag_service

# NEW:
from services.external_ai_service import ExternalAIService
from database import SessionLocal

# Lines 36-48 - Lifespan function
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Replaces deprecated on_event decorator.
    """
    # OLD:
    # logger.info("✓ Application startup - validating Akvo RAG configuration")
    # rag_service = get_akvo_rag_service()
    # if not rag_service.is_configured():
    #     logger.warning(
    #         "⚠ Akvo RAG not fully configured. "
    #         "Set AKVO_RAG_APP_ACCESS_TOKEN and "
    #         "AKVO_RAG_APP_KNOWLEDGE_BASE_ID environment variables."
    #     )
    # else:
    #     logger.info(
    #         f"✓ Akvo RAG configured with KB ID: "
    #         f"{rag_service.knowledge_base_id}"
    #     )

    # NEW:
    logger.info("✓ Application startup - validating AI service configuration")
    db = SessionLocal()
    try:
        ai_service = ExternalAIService(db)
        if not ai_service.is_configured():
            logger.warning(
                "⚠ External AI service not configured. "
                "Create an active service token via /api/admin/service-tokens"
            )
        else:
            logger.info(
                f"✓ External AI service configured: "
                f"{ai_service.token.service_name} "
                f"(chat: {ai_service.token.chat_url})"
            )
    finally:
        db.close()

    yield

    # Shutdown: cleanup if needed
    logger.info("✓ Application shutdown")
```

#### Step 2.3: Update `routers/service_tokens.py` - Cache Invalidation

**File:** `backend/routers/service_tokens.py`

**Changes:** Add cache invalidation when tokens are created/updated

```python
from services.external_ai_service import ExternalAIService

# In create_service_token function (after line 73):
service_token = ServiceTokenService.create_token(
    db,
    token_data.service_name,
    token_data.access_token,
    token_data.chat_url,
    token_data.upload_url,
    token_data.active,
)

# ADD: Invalidate cache when new token is created
ExternalAIService.invalidate_cache()

return ServiceTokenResponse.model_validate(service_token)


# In update_service_token function (after line 103):
updated_token = ServiceTokenService.update_token_config(
    db,
    token_id,
    token_data.access_token,
    token_data.chat_url,
    token_data.upload_url,
    token_data.active,
)

if not updated_token:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Service token not found",
    )

# ADD: Invalidate cache when token is updated
ExternalAIService.invalidate_cache()

return ServiceTokenResponse.model_validate(updated_token)
```

#### Step 2.4: Update `knowledge_base.py` - Remove TODO

**File:** `backend/routers/knowledge_base.py`

**Lines to change:** 36, 43, 84-86

```python
# Lines 36, 43 - Update docstring
# OLD:
description="Upload a file and create a knowledge base entry. "
           "The file will be processed by Akvo RAG service.",

# NEW:
description="Upload a file and create a knowledge base entry. "
           "The file will be processed by the configured external AI service.",


# Lines 84-86 - Replace TODO
# OLD:
# TODO: Send file to Akvo RAG service for processing
# This would typically involve uploading to external service
# and getting a job_id back

# NEW:
from services.external_ai_service import ExternalAIService

# Send file to external AI service for processing
ai_service = ExternalAIService(db)
if ai_service.is_configured() and ai_service.token.upload_url:
    # TODO: Implement file upload when ready
    # job_response = await ai_service.create_upload_job(
    #     file_path=...,
    #     kb_id=kb.id,
    #     metadata=extra_data
    # )
    pass
```

---

### Phase 3: Clean Up Environment Variables

**Goal:** Remove redundant environment variables

#### Step 3.1: Update `.env.example`

**File:** `.env.example`

**Changes:**

```bash
# REMOVE THESE - now in database via service_tokens table
# AKVO_RAG_APP_ACCESS_TOKEN=your_akvo_rag_access_token_here
# AKVO_RAG_APP_KNOWLEDGE_BASE_ID=your_akvo_rag_knowledge_base_id_here

# ALSO REMOVE - development-specific, not needed in example
# IP_ADDRESS=http://192.168.1.19:3000/api

# KEEP THESE - infrastructure/deployment settings
# Akvo RAG Service Configuration
AKVO_RAG_BASE_URL=https://agriconnect-rag.akvotest.org
AKVO_RAG_APP_NAME=agriconnect
AKVO_RAG_APP_DOMAIN=https://yourdomain.com
AKVO_RAG_APP_CHAT_CALLBACK=https://yourdomain.com/api/callback/ai
AKVO_RAG_APP_UPLOAD_CALLBACK=https://yourdomain.com/api/callback/kb

# WhatsApp template SIDs remain unchanged
WHATSAPP_CONFIRMATION_TEMPLATE_SID=your_whatsapp_confirmation_template_sid_here
WHATSAPP_RECONNECTION_TEMPLATE_SID=your_whatsapp_reconnection_template_sid_here
```

#### Step 3.2: Update `docker-compose.yml`

**File:** `docker-compose.yml`

**Changes:** Remove lines 39-40

```yaml
backend:
  # ... existing config ...
  environment:
    - DATABASE_URL=postgresql://akvo:password@db:5432/agriconnect
    - SECRET_KEY=09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7
    - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
    - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
    - TWILIO_WHATSAPP_NUMBER=${TWILIO_WHATSAPP_NUMBER:-whatsapp:+14155238886}
    - SMTP_HOST=${SMTP_HOST}
    - SMTP_PORT=${SMTP_PORT}
    - SMTP_USER=${SMTP_USER}
    - SMTP_PASS=${SMTP_PASS}
    - SMTP_USE_TLS=${SMTP_USE_TLS}
    - WEBDOMAIN=${WEBDOMAIN:-localhost}
    - STORAGE_SECRET=${STORAGE_SECRET}
    - AKVO_RAG_BASE_URL=${AKVO_RAG_BASE_URL}
    - AKVO_RAG_APP_NAME=${AKVO_RAG_APP_NAME}
    - AKVO_RAG_APP_DOMAIN=${AKVO_RAG_APP_DOMAIN}
    - AKVO_RAG_APP_CHAT_CALLBACK=${AKVO_RAG_APP_CHAT_CALLBACK}
    - AKVO_RAG_APP_UPLOAD_CALLBACK=${AKVO_RAG_APP_UPLOAD_CALLBACK}
    # REMOVE THESE:
    # - AKVO_RAG_APP_ACCESS_TOKEN=${AKVO_RAG_APP_ACCESS_TOKEN}
    # - AKVO_RAG_APP_KNOWLEDGE_BASE_ID=${AKVO_RAG_APP_KNOWLEDGE_BASE_ID}
    - WHATSAPP_CONFIRMATION_TEMPLATE_SID=${WHATSAPP_CONFIRMATION_TEMPLATE_SID}
```

#### Step 3.3: Update Local `.env`

**File:** `.env` (local, not committed)

**Action:** Remove the following lines:
```bash
# REMOVE - now in database
AKVO_RAG_APP_ACCESS_TOKEN=...
AKVO_RAG_APP_KNOWLEDGE_BASE_ID=...

# REMOVE - development-specific
IP_ADDRESS=...
```

**Important:** Ensure `.env` is in `.gitignore` to prevent committing sensitive data.

---

### Phase 4: Database Migration & Data Seeding

**Goal:** Migrate existing environment variable tokens to database

#### Step 4.1: Create Alembic Migration

**File:** `backend/alembic/versions/2025_10_30_XXXX-seed_initial_service_token.py`

**Purpose:** Migrate existing `AKVO_RAG_APP_ACCESS_TOKEN` from environment to database

```python
"""Seed initial Akvo RAG service token from environment variables

Revision ID: seed_initial_service_token
Revises: <previous_migration_id>
Create Date: 2025-10-30 XX:XX:XX
"""
from alembic import op
import sqlalchemy as sa
import os
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'seed_initial_service_token'
down_revision = '<previous_migration_id>'  # Update with actual previous migration
branch_labels = None
depends_on = None


def upgrade():
    """
    Migrate existing AKVO_RAG environment variables to service_tokens table.

    This migration checks if AKVO_RAG_APP_ACCESS_TOKEN exists in environment
    and creates a service token in the database if it does.
    """
    # Check if AKVO_RAG_APP_ACCESS_TOKEN exists in env
    access_token = os.getenv('AKVO_RAG_APP_ACCESS_TOKEN')

    if access_token:
        # Connection for raw SQL
        connection = op.get_bind()

        # Check if service token already exists
        result = connection.execute(
            sa.text("SELECT id FROM service_tokens WHERE service_name = 'akvo-rag'")
        )
        existing = result.fetchone()

        if not existing:
            # Insert initial service token
            connection.execute(
                sa.text("""
                    INSERT INTO service_tokens
                    (service_name, access_token, chat_url, upload_url, active, created_at, updated_at)
                    VALUES (
                        :service_name,
                        :access_token,
                        :chat_url,
                        :upload_url,
                        :active,
                        :created_at,
                        :updated_at
                    )
                """),
                {
                    'service_name': 'akvo-rag',
                    'access_token': access_token,
                    'chat_url': 'https://agriconnect-rag.akvotest.org/api/apps/jobs',
                    'upload_url': 'https://agriconnect-rag.akvotest.org/api/apps/upload',
                    'active': 1,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
            )
            print("✓ Migrated AKVO_RAG_APP_ACCESS_TOKEN to database (service_tokens table)")
        else:
            print("✓ Service token 'akvo-rag' already exists, skipping migration")
    else:
        print("⚠ AKVO_RAG_APP_ACCESS_TOKEN not found in environment, skipping migration")
        print("  You can create service tokens manually via /api/admin/service-tokens")


def downgrade():
    """
    Remove the seeded service token.

    Note: This will only remove the specific 'akvo-rag' service token created
    by this migration. User-created tokens will not be affected.
    """
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM service_tokens WHERE service_name = 'akvo-rag'")
    )
    print("✓ Removed 'akvo-rag' service token")
```

**Usage:**
```bash
# Run migration
./dc.sh exec backend alembic upgrade head

# Rollback if needed
./dc.sh exec backend alembic downgrade -1
```

---

### Phase 5: Update Tests

**Goal:** Update test files to use new generic service

#### Step 5.1: Rename Test File

**Action:**
```bash
mv backend/tests/test_akvo_rag_service.py backend/tests/test_external_ai_service.py
```

#### Step 5.2: Update `test_external_ai_service.py`

**File:** `backend/tests/test_external_ai_service.py` (formerly `test_akvo_rag_service.py`)

**Changes:**

```python
# OLD imports:
from services.akvo_rag_service import AkvoRagService, get_akvo_rag_service

# NEW imports:
from services.external_ai_service import ExternalAIService, get_external_ai_service
from services.service_token_service import ServiceTokenService

# Update test fixtures to create service tokens in database:
@pytest.fixture
def mock_service_token(db):
    """Create a mock service token in database"""
    token = ServiceTokenService.create_token(
        db,
        service_name="test-ai-service",
        access_token="test_token_123",
        chat_url="https://test-ai.example.com/api/chat",
        upload_url="https://test-ai.example.com/api/upload",
        active=1
    )
    yield token
    # Cleanup
    ServiceTokenService.delete_token(db, token.id)

# Update all test functions to use ExternalAIService instead of AkvoRagService
```

#### Step 5.3: Update `test_whatsapp_akvo_rag.py`

**File:** `backend/tests/test_whatsapp_akvo_rag.py`

**Changes:**

```python
# Update imports
from services.external_ai_service import ExternalAIService

# Update mocking to use ExternalAIService
@pytest.fixture
def mock_ai_service(mocker):
    """Mock external AI service"""
    mock = mocker.patch('services.external_ai_service.ExternalAIService')
    # ... rest of mock setup
    return mock
```

#### Step 5.4: Update `conftest.py`

**File:** `backend/tests/conftest.py`

**Changes:**

```python
# Add fixture for service token
@pytest.fixture
def test_service_token(db):
    """Create a test service token"""
    from services.service_token_service import ServiceTokenService

    token = ServiceTokenService.create_token(
        db,
        service_name="test-service",
        access_token="test_access_token",
        chat_url="https://test.example.com/chat",
        upload_url="https://test.example.com/upload",
        active=1
    )
    yield token
    # Cleanup
    ServiceTokenService.delete_token(db, token.id)
```

---

### Phase 6: Documentation Updates

**Goal:** Update documentation to reflect new architecture

#### Step 6.1: Update `CLAUDE.md`

**File:** `CLAUDE.md`

**Section to update:** "API Architecture" and "Required Environment Variables"

**Changes:**

```markdown
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

**Environment Variables (Infrastructure only):**
- `AKVO_RAG_BASE_URL` - Base URL of AI service (infrastructure)
- `AKVO_RAG_APP_NAME` - App identifier for registration
- `AKVO_RAG_APP_DOMAIN` - Domain for callbacks
- `AKVO_RAG_APP_CHAT_CALLBACK` - Chat callback URL
- `AKVO_RAG_APP_UPLOAD_CALLBACK` - Upload callback URL

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
    access_token VARCHAR,           -- Token to authenticate with external service
    chat_url VARCHAR,                -- URL for chat job requests
    upload_url VARCHAR,              -- URL for KB upload job requests
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
```

#### Step 6.2: Create Migration Guide

**File:** `docs/MIGRATION_GUIDE_EXTERNAL_AI_SERVICE.md`

```markdown
# Migration Guide: External AI Service Integration

## For Developers

### What Changed?

1. **Service renamed:**
   - `AkvoRagService` → `ExternalAIService` (generic, service-agnostic)

2. **Configuration moved to database:**
   - Access tokens no longer in environment variables
   - Configuration stored in `service_tokens` table
   - Managed via `/api/admin/service-tokens` API

3. **Import changes:**
   ```python
   # OLD:
   from services.akvo_rag_service import get_akvo_rag_service

   # NEW:
   from services.external_ai_service import get_external_ai_service
   ```

4. **Usage changes:**
   ```python
   # OLD:
   rag_service = get_akvo_rag_service()  # No DB needed

   # NEW:
   ai_service = get_external_ai_service(db)  # Pass DB session
   ```

### API Compatibility

The API is 100% backward compatible. All method signatures remain the same:

```python
# Same method calls, no changes needed:
await ai_service.create_chat_job(
    message_id=message_id,
    message_type=MessageType.REPLY.value,
    customer_id=customer.id,
    chats=chats,
    trace_id=trace_id
)
```

## For DevOps / Deployment

### Environment Variable Changes

**Remove these from `.env` and deployment configs:**
```bash
# REMOVE - now in database:
AKVO_RAG_APP_ACCESS_TOKEN=...
AKVO_RAG_APP_KNOWLEDGE_BASE_ID=...

# REMOVE - development-specific:
IP_ADDRESS=...
```

**Keep these (infrastructure settings):**
```bash
AKVO_RAG_BASE_URL=https://agriconnect-rag.akvotest.org
AKVO_RAG_APP_NAME=agriconnect
AKVO_RAG_APP_DOMAIN=https://yourdomain.com
AKVO_RAG_APP_CHAT_CALLBACK=https://yourdomain.com/api/callback/ai
AKVO_RAG_APP_UPLOAD_CALLBACK=https://yourdomain.com/api/callback/kb
```

### Migration Steps

1. **Before deployment:**
   ```bash
   # Ensure AKVO_RAG_APP_ACCESS_TOKEN is set in current environment
   echo $AKVO_RAG_APP_ACCESS_TOKEN
   ```

2. **Deploy new code:**
   ```bash
   git pull origin main
   ./dc.sh down
   ./dc.sh up -d
   ```

3. **Run database migration:**
   ```bash
   # This automatically migrates AKVO_RAG_APP_ACCESS_TOKEN to database
   ./dc.sh exec backend alembic upgrade head
   ```

4. **Verify migration:**
   ```bash
   # Check service token was created
   curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
     http://localhost:8000/api/admin/service-tokens
   ```

5. **Remove environment variables:**
   ```bash
   # Edit .env file and remove:
   # - AKVO_RAG_APP_ACCESS_TOKEN
   # - AKVO_RAG_APP_KNOWLEDGE_BASE_ID
   # - IP_ADDRESS
   ```

6. **Restart services:**
   ```bash
   ./dc.sh restart backend
   ```

## For Admins

### Managing Service Tokens via API

**Create a new service token:**
```bash
curl -X POST http://localhost:8000/api/admin/service-tokens \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "akvo-rag",
    "access_token": "your_access_token_here",
    "chat_url": "https://agriconnect-rag.akvotest.org/api/apps/jobs",
    "upload_url": "https://agriconnect-rag.akvotest.org/api/apps/upload",
    "active": 1
  }'
```

**List all service tokens:**
```bash
curl http://localhost:8000/api/admin/service-tokens \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Update a service token:**
```bash
curl -X PUT http://localhost:8000/api/admin/service-tokens/1 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "new_token_here",
    "active": 1
  }'
```

**Switch to a different AI service:**
```bash
# Deactivate current service
curl -X PUT http://localhost:8000/api/admin/service-tokens/1 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"active": 0}'

# Activate new service
curl -X PUT http://localhost:8000/api/admin/service-tokens/2 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"active": 1}'
```

## Troubleshooting

### "External AI service not configured" on startup

**Cause:** No active service token in database

**Solution:**
```bash
# Check if service token exists
./dc.sh exec backend python -c "
from database import SessionLocal
from services.service_token_service import ServiceTokenService
db = SessionLocal()
token = ServiceTokenService.get_active_token(db)
print(f'Active token: {token.service_name if token else None}')
"

# If no token, run migration or create manually via API
```

### Cache not updating after token change

**Cause:** TTL cache not expired yet (5 minutes)

**Solution:** Restart backend service to clear cache:
```bash
./dc.sh restart backend
```

Or wait 5 minutes for cache to expire automatically.
```

---

## 🔄 Implementation Checklist

### Phase 1: Create Generic Service
- [ ] Create `backend/services/external_ai_service.py`
- [ ] Update `backend/config.py` (remove token env vars lines 77-85)
- [ ] Test service initialization with mock DB

### Phase 2: Migration
- [ ] Update `backend/routers/whatsapp.py` (lines 21, 181, 305, 389)
- [ ] Update `backend/main.py` (lines 23, 36-48)
- [ ] Update `backend/routers/service_tokens.py` (cache invalidation)
- [ ] Update `backend/routers/knowledge_base.py` (lines 36, 43, 84-86)

### Phase 3: Environment Variables
- [ ] Update `.env.example` (remove redundant vars)
- [ ] Update `docker-compose.yml` (remove lines 39-40)
- [ ] Update local `.env` (remove sensitive tokens)
- [ ] Verify `.env` is in `.gitignore`

### Phase 4: Database
- [ ] Create Alembic migration `seed_initial_service_token.py`
- [ ] Test migration with existing `AKVO_RAG_APP_ACCESS_TOKEN`
- [ ] Test migration without env var (should skip gracefully)
- [ ] Run migration: `./dc.sh exec backend alembic upgrade head`

### Phase 5: Tests
- [ ] Rename `test_akvo_rag_service.py` → `test_external_ai_service.py`
- [ ] Update test imports and fixtures
- [ ] Update `test_whatsapp_akvo_rag.py`
- [ ] Update `conftest.py`
- [ ] Run all tests: `./dc.sh exec backend pytest`

### Phase 6: Documentation
- [ ] Update `CLAUDE.md` (API Architecture section)
- [ ] Create `docs/MIGRATION_GUIDE_EXTERNAL_AI_SERVICE.md`
- [ ] Update this refactoring plan status

### Phase 7: Cleanup
- [ ] Mark `backend/services/akvo_rag_service.py` as deprecated (add comment)
- [ ] Schedule removal of deprecated service (1-2 sprints later)
- [ ] Update API documentation (Swagger/OpenAPI)

### Phase 8: Verification
- [ ] All tests pass
- [ ] Backend starts successfully
- [ ] Service token visible in admin API
- [ ] WhatsApp messages trigger AI jobs
- [ ] AI callbacks work correctly
- [ ] Cache invalidation works on token updates
- [ ] No breaking changes for existing functionality

---

## ✅ Success Criteria

1. **✅ No breaking changes** - Everything continues working during and after migration
2. **✅ Service tokens from database** - No more environment variables for tokens
3. **✅ Generic & extensible** - Can switch AI services via database without code changes
4. **✅ Performance optimized** - 5-minute TTL cache reduces DB queries
5. **✅ All tests pass** - No regressions in existing functionality
6. **✅ Documentation complete** - Clear migration guide for developers and ops
7. **✅ Environment cleaned** - No redundant or sensitive data in env files

---

## 📊 Rollback Plan

If issues occur during migration:

1. **Rollback database migration:**
   ```bash
   ./dc.sh exec backend alembic downgrade -1
   ```

2. **Revert code changes:**
   ```bash
   git revert <commit_hash>
   ./dc.sh restart backend
   ```

3. **Restore environment variables:**
   - Re-add `AKVO_RAG_APP_ACCESS_TOKEN` to `.env`
   - Re-add to `docker-compose.yml`

4. **Restart services:**
   ```bash
   ./dc.sh down
   ./dc.sh up -d
   ```

---

## 📝 Notes

- **IP_ADDRESS environment variable** is also removed as part of this refactoring (it's development-specific and shouldn't be in shared config)
- **Backward compatibility** is maintained throughout - no API changes required
- **Cache strategy** (5-minute TTL) balances performance and freshness
- **Migration is idempotent** - can be run multiple times safely
- **Service tokens support multiple providers** - easy to switch between Akvo RAG, OpenAI, Claude, etc.

---

## 🎯 Next Steps

After completing this refactoring:

1. **Add support for multiple AI providers** (OpenAI, Claude, etc.)
2. **Implement upload job functionality** (`create_upload_job` method)
3. **Add service health checks** (ping external services periodically)
4. **Create admin UI** for managing service tokens (instead of just API)
5. **Add metrics/monitoring** for AI service performance

---

**Status:** Ready for Implementation
**Estimated Effort:** 1-2 days
**Risk Level:** Low (backward compatible, no breaking changes)
