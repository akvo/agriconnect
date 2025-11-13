# Broadcast API - Twilio Integration & Queue Management
**Plan 2 of 2**

## 🔑 Key Design Decisions

### Status Tracking with DeliveryStatus

This plan uses the existing `DeliveryStatus` enum from `models/message.py` instead of creating a separate `BroadcastStatus` enum.

**Import Statement:**
```python
from models.message import DeliveryStatus
```

**Status Values:**
- `DeliveryStatus.PENDING` - Initial state, not sent yet
- `DeliveryStatus.QUEUED` - Twilio accepted, queuing
- `DeliveryStatus.SENDING` - Twilio sending to WhatsApp
- `DeliveryStatus.SENT` - Sent to WhatsApp servers
- `DeliveryStatus.DELIVERED` - Delivered to device
- `DeliveryStatus.READ` - Customer read message
- `DeliveryStatus.FAILED` - Permanent failure
- `DeliveryStatus.UNDELIVERED` - Temporary failure/expired

**Confirmation Logic:**
- User confirmation tracked via `confirmed_at` timestamp, NOT status enum
- When user clicks "Yes": `confirmed_at = datetime.utcnow()` (status remains SENT)
- Query for awaiting confirmation: `WHERE status = SENT AND confirmed_at IS NULL`
- Query for confirmed: `WHERE confirmed_at IS NOT NULL`

**Two-Step Flow:**
```
1. Template sent    → status = SENT, confirmed_at = NULL
2. User clicks "Yes" → status = SENT, confirmed_at = timestamp
3. Actual message    → status = SENT (until Twilio callback)
4. Twilio callback   → status = DELIVERED
```

---

## Overview

This plan covers Phase 5-7 of the Broadcast API implementation:
- Celery queue system setup with Redis
- Twilio WhatsApp integration using existing services
- Webhook handlers for confirmation and status tracking
- Robust retry mechanism for failed/undelivered messages
- Integration tests and operations guide

**Prerequisites**: Plan 1 must be completed (database models, schemas, core API endpoints)

---

## Phase 5: Celery Setup & Queue Infrastructure

### 5.1 Install Dependencies

**File: `backend/requirements.txt`**

Add:
```txt
celery==5.3.4
redis==5.0.1
```

### 5.2 Celery Application Configuration

**File: `backend/celery_app.py`** (NEW)

```python
"""
Celery application configuration for AgriConnect.
Handles broadcast message queue processing with Redis broker.
"""
import logging
from celery import Celery
from celery.schedules import crontab
from config import settings

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "agriconnect",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # Soft limit at 4 minutes
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    broker_connection_retry_on_startup=True,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "retry-failed-broadcasts": {
        "task": "tasks.broadcast_tasks.retry_failed_broadcasts",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks(["tasks"])

logger.info("Celery app initialized with Redis broker")
```

### 5.3 Configuration Updates

**File: `backend/config.py`**

Add to settings class:
```python
# Celery Configuration
celery_broker_url: str = "redis://redis:6379/0"
celery_result_backend: str = "redis://redis:6379/0"

# Broadcast Configuration
broadcast_template_sid: str = ""  # Twilio template content SID
broadcast_confirmation_button_payload: str = "read_broadcast"
broadcast_batch_size: int = 50  # Max recipients per batch
broadcast_retry_intervals: List[int] = [5, 15, 60]  # Minutes: 5, 15, 60
```

### 5.4 Docker Compose Updates

**File: `docker-compose.yml`**

Add Redis and Celery services:
```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: agriconnect-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: agriconnect-celery-worker
    command: celery -A celery_app worker --loglevel=info
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: agriconnect-celery-beat
    command: celery -A celery_app beat --loglevel=info
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0

volumes:
  redis-data:
```

### 5.5 Phase 5 Checklist

- [ ] Add Celery and Redis dependencies to requirements.txt
- [ ] Create `backend/celery_app.py` with configuration
- [ ] Update `backend/config.py` with Celery settings
- [ ] Update `docker-compose.yml` with Redis, worker, beat services
- [ ] Test Redis connection: `docker-compose up redis`
- [ ] Test Celery worker: `docker-compose up celery-worker`
- [ ] Test Celery beat: `docker-compose up celery-beat`
- [ ] Verify worker logs show task autodiscovery

**Success Criteria:**
- ✅ Redis service starts and healthcheck passes
- ✅ Celery worker connects to Redis broker
- ✅ Celery beat scheduler starts without errors
- ✅ Worker logs show "agriconnect@worker ready"

---

## Phase 6: Broadcast Tasks & Twilio Integration

### 6.1 Broadcast Celery Tasks

**File: `backend/tasks/__init__.py`** (NEW)

```python
"""Celery tasks package for AgriConnect."""
```

**File: `backend/tasks/broadcast_tasks.py`** (NEW)

```python
"""
Broadcast message processing tasks.
Handles template sending, confirmation processing, and retry logic.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from celery_app import celery_app
from database import SessionLocal
from models.broadcast import (
    BroadcastMessage,
    BroadcastRecipient,
)
from models.message import Message, MessageType, MessageFrom, MessageStatus, DeliveryStatus
from services.whatsapp_service import WhatsAppService
from config import settings

logger = logging.getLogger(__name__)


def get_db():
    """Get database session for tasks."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(
    name="tasks.broadcast_tasks.process_broadcast",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_broadcast(self, broadcast_id: int):
    """
    Main broadcast processing task.
    Sends template messages to all contacts in batches.

    Args:
        broadcast_id: ID of the broadcast message to process
    """
    db = next(get_db())

    try:
        # Get broadcast message
        broadcast = (
            db.query(BroadcastMessage)
            .filter(BroadcastMessage.id == broadcast_id)
            .first()
        )

        if not broadcast:
            logger.error(f"Broadcast {broadcast_id} not found")
            return {"error": "Broadcast not found"}

        # Get pending contacts
        contacts = (
            db.query(BroadcastRecipient)
            .filter(
                BroadcastRecipient.broadcast_message_id == broadcast_id,
                BroadcastRecipient.status == DeliveryStatus.PENDING,
            )
            .limit(settings.broadcast_batch_size)
            .all()
        )

        if not contacts:
            logger.info(f"No pending contacts for broadcast {broadcast_id}")
            return {"message": "No pending contacts"}

        logger.info(
            f"Processing broadcast {broadcast_id} "
            f"for {len(contacts)} contacts"
        )

        # Process each contact
        whatsapp_service = WhatsAppService()
        sent_count = 0
        failed_count = 0

        for contact in contacts:
            try:
                # Send template message using existing service
                result = whatsapp_service.send_template_message(
                    to=contact.customer.phone_number,
                    content_sid=settings.broadcast_template_sid,
                    content_variables={
                        "1": contact.customer.full_name or "Farmer",
                    },
                )

                # Update contact status
                contact.status = DeliveryStatus.SENT
                contact.template_message_sid = result["sid"]
                contact.sent_at = datetime.utcnow()

                sent_count += 1
                logger.info(
                    f"Template sent to {contact.customer.phone_number}: "
                    f"{result['sid']}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send template to "
                    f"{contact.customer.phone_number}: {e}"
                )
                contact.status = DeliveryStatus.FAILED
                contact.error_message = str(e)
                failed_count += 1

        db.commit()

        # If there are more pending contacts, requeue task
        remaining = (
            db.query(BroadcastRecipient)
            .filter(
                BroadcastRecipient.broadcast_message_id == broadcast_id,
                BroadcastRecipient.status == DeliveryStatus.PENDING,
            )
            .count()
        )

        if remaining > 0:
            logger.info(
                f"Requeuing broadcast {broadcast_id}, "
                f"{remaining} contacts remaining"
            )
            process_broadcast.apply_async(
                args=[broadcast_id],
                countdown=2,  # 2 second delay between batches
            )

        return {
            "broadcast_id": broadcast_id,
            "sent": sent_count,
            "failed": failed_count,
            "remaining": remaining,
        }

    except Exception as e:
        logger.error(f"Error processing broadcast {broadcast_id}: {e}")
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(
    name="tasks.broadcast_tasks.send_actual_message",
    bind=True,
    max_retries=3,
)
def send_actual_message(
    self,
    broadcast_contact_id: int,
    customer_phone: str,
    message_body: str,
):
    """
    Send actual broadcast message after user confirmation.
    Creates individual Message record for message history.

    Args:
        broadcast_contact_id: ID of the broadcast contact
        customer_phone: Customer phone number
        message_body: Message content
    """
    db = next(get_db())

    try:
        # Get broadcast contact
        contact = (
            db.query(BroadcastRecipient)
            .filter(BroadcastRecipient.id == broadcast_contact_id)
            .first()
        )

        if not contact:
            logger.error(f"Broadcast contact {broadcast_contact_id} not found")
            return {"error": "Contact not found"}

        # Prepare message with [Broadcast] prefix (from rag-doll pattern)
        customer_name = contact.customer.full_name or "Farmer"
        formatted_message = f"[Broadcast]\n\nHi {customer_name},\n{message_body}"

        # Send message using existing service
        whatsapp_service = WhatsAppService()
        result = whatsapp_service.send_message(customer_phone, formatted_message)

        # Create Message record for history
        message = Message(
            message_sid=result["sid"],
            customer_id=contact.customer_id,
            body=message_body,  # Store original without prefix
            from_source=MessageFrom.USER,  # Sent by EO
            message_type=MessageType.BROADCAST,
            status=MessageStatus.SENT,
        )
        db.add(message)

        # Update broadcast contact (status remains SENT until Twilio confirms delivery)
        contact.actual_message_sid = result["sid"]
        contact.message_id = message.id

        db.commit()

        logger.info(
            f"Broadcast message sent to {customer_phone}: {result['sid']}"
        )

        return {
            "contact_id": broadcast_contact_id,
            "message_sid": result["sid"],
            "status": "sent",
        }

    except Exception as e:
        logger.error(
            f"Error sending broadcast message to {customer_phone}: {e}"
        )
        db.rollback()

        # Update contact status to failed
        if contact:
            contact.status = DeliveryStatus.FAILED
            contact.error_message = str(e)
            db.commit()

        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(name="tasks.broadcast_tasks.retry_failed_broadcasts")
def retry_failed_broadcasts():
    """
    Periodic task to retry failed/undelivered broadcast messages.
    Runs every 5 minutes via Celery Beat.

    Only retries messages with status FAILED or UNDELIVERED.
    Uses exponential backoff: 5min, 15min, 60min.
    """
    db = next(get_db())

    try:
        now = datetime.utcnow()
        retry_intervals = settings.broadcast_retry_intervals  # [5, 15, 60]

        # Find contacts eligible for retry
        # Status must be FAILED or UNDELIVERED (not SENT or DELIVERED)
        for retry_count in range(len(retry_intervals)):
            retry_window = timedelta(minutes=retry_intervals[retry_count])

            contacts = (
                db.query(BroadcastRecipient)
                .filter(
                    BroadcastRecipient.status.in_([
                        DeliveryStatus.FAILED,
                        DeliveryStatus.UNDELIVERED,
                    ]),
                    BroadcastRecipient.retry_count == retry_count,
                    BroadcastRecipient.sent_at.isnot(None),
                    BroadcastRecipient.sent_at <= now - retry_window,
                )
                .limit(50)  # Batch size
                .all()
            )

            if not contacts:
                continue

            logger.info(
                f"Retrying {len(contacts)} contacts at retry attempt "
                f"{retry_count + 1} (after {retry_intervals[retry_count]}min)"
            )

            whatsapp_service = WhatsAppService()

            for contact in contacts:
                try:
                    # Retry template message
                    result = whatsapp_service.send_template_message(
                        to=contact.customer.phone_number,
                        content_sid=settings.broadcast_template_sid,
                        content_variables={
                            "1": contact.customer.full_name or "Farmer",
                        },
                    )

                    # Update contact
                    contact.template_message_sid = result["sid"]
                    contact.retry_count += 1
                    contact.sent_at = datetime.utcnow()
                    contact.status = DeliveryStatus.SENT
                    contact.error_message = None

                    logger.info(
                        f"Retry successful for contact {contact.id}: "
                        f"{result['sid']}"
                    )

                except Exception as e:
                    logger.error(
                        f"Retry failed for contact {contact.id}: {e}"
                    )
                    contact.retry_count += 1
                    contact.error_message = str(e)

                    # Mark as permanently failed after max retries
                    if contact.retry_count >= len(retry_intervals):
                        contact.status = DeliveryStatus.FAILED
                        logger.warning(
                            f"Contact {contact.id} reached max retries, "
                            f"marking as permanently failed"
                        )

            db.commit()

        return {"message": "Retry task completed"}

    except Exception as e:
        logger.error(f"Error in retry task: {e}")
        db.rollback()
        raise
    finally:
        db.close()
```

### 6.2 Update Broadcast Service

**File: `backend/services/broadcast_service.py`**

Update the `send_broadcast()` method to queue Celery task:

```python
from tasks.broadcast_tasks import process_broadcast

# In BroadcastService class, update send_broadcast method:

def send_broadcast(
    self, broadcast_id: int, user: AdminUser
) -> BroadcastMessage:
    """
    Queue broadcast message for processing.

    Args:
        broadcast_id: ID of the broadcast message
        user: Admin user sending the broadcast

    Returns:
        BroadcastMessage with queued status
    """
    broadcast = (
        self.db.query(BroadcastMessage)
        .filter(BroadcastMessage.id == broadcast_id)
        .first()
    )

    if not broadcast:
        raise ValueError("Broadcast not found")

    # Verify user has access to all groups
    for msg_group in broadcast.broadcast_groups:
        group = msg_group.broadcast_group
        if group.administrative_id != user.administrative_id:
            raise ValueError(
                f"No access to group {group.name} "
                f"in ward {group.administrative.name}"
            )

    # Verify broadcast has contacts
    if not broadcast.broadcast_recipients:
        raise ValueError("No contacts in broadcast groups")

    # Update status and queue for processing
    broadcast.status = "processing"
    broadcast.queued_at = datetime.utcnow()
    self.db.commit()

    # Queue Celery task
    process_broadcast.apply_async(args=[broadcast_id])

    logger.info(
        f"Broadcast {broadcast_id} queued for processing "
        f"with {len(broadcast.broadcast_recipients)} contacts"
    )

    return broadcast
```

### 6.3 WhatsApp Webhook Updates

**File: `backend/routers/whatsapp.py`**

Add broadcast confirmation handler in the existing webhook:

```python
# Add after line 138 (escalate_payload definition):

broadcast_confirmation_payload = settings.broadcast_confirmation_button_payload

# Add after line 274 (escalate button handler), before FLOW 1:

# ========================================
# FLOW 3: Handle broadcast confirmation button
# ========================================
if ButtonPayload == broadcast_confirmation_payload:
    logger.info(f"Customer {phone_number} confirmed broadcast read")

    # Find pending broadcast contact (status = SENT, not yet confirmed)
    from models.broadcast import BroadcastRecipient
    from models.message import DeliveryStatus
    from tasks.broadcast_tasks import send_actual_message

    broadcast_contact = (
        db.query(BroadcastRecipient)
        .filter(
            BroadcastRecipient.customer_id == customer.id,
            BroadcastRecipient.status == DeliveryStatus.SENT,
            BroadcastRecipient.confirmed_at.is_(None),  # Not yet confirmed
        )
        .order_by(BroadcastRecipient.sent_at.desc())
        .first()
    )

    if broadcast_contact:
        # Mark as confirmed (status remains SENT)
        broadcast_contact.confirmed_at = datetime.utcnow()
        db.commit()

        # Queue actual message sending
        send_actual_message.apply_async(
            args=[
                broadcast_contact.id,
                customer.phone_number,
                broadcast_contact.broadcast_message.message,
            ]
        )

        logger.info(
            f"Queued actual broadcast message for "
            f"contact {broadcast_contact.id}"
        )

        return {
            "status": "success",
            "message": "Broadcast confirmation processed",
        }
    else:
        logger.warning(
            f"No pending broadcast found for {phone_number}"
        )
        return {
            "status": "ignored",
            "message": "No pending broadcast",
        }
```

### 6.4 Status Callback Updates

**File: `backend/routers/whatsapp.py`**

Update the status callback handler (line 472-532) to handle broadcast messages:

```python
# In whatsapp_status_callback function, after line 526:

# Check if this is a broadcast message
from models.broadcast import BroadcastRecipient
from models.message import DeliveryStatus

# Try to find broadcast contact by message_sid
broadcast_contact = None

# Check template message SID
broadcast_contact = (
    db.query(BroadcastRecipient)
    .filter(BroadcastRecipient.template_message_sid == MessageSid)
    .first()
)

if not broadcast_contact:
    # Check actual message SID
    broadcast_contact = (
        db.query(BroadcastRecipient)
        .filter(BroadcastRecipient.actual_message_sid == MessageSid)
        .first()
    )

if broadcast_contact:
    logger.info(
        f"Updating broadcast contact {broadcast_contact.id} "
        f"status to {MessageStatus}"
    )

    # Update broadcast contact status based on Twilio status
    if status_enum == TwilioMessageStatus.DELIVERED:
        broadcast_contact.status = DeliveryStatus.DELIVERED
        broadcast_contact.delivered_at = datetime.utcnow()
    elif status_enum == TwilioMessageStatus.FAILED:
        broadcast_contact.status = DeliveryStatus.FAILED
        broadcast_contact.error_message = ErrorMessage
    elif status_enum == TwilioMessageStatus.UNDELIVERED:
        broadcast_contact.status = DeliveryStatus.UNDELIVERED
        broadcast_contact.error_message = ErrorMessage
    elif status_enum == TwilioMessageStatus.READ:
        broadcast_contact.status = DeliveryStatus.READ
        broadcast_contact.read_at = datetime.utcnow()

    db.commit()

    return {
        "status": "success",
        "message": "Broadcast status updated",
        "broadcast_contact_id": broadcast_contact.id,
    }

# Continue with existing status processing for non-broadcast messages...
```

### 6.5 Delete Old Retry Service

**Files to DELETE:**
- `backend/services/retry_service.py`
- `backend/tests/test_retry_service.py`

```bash
# Run these commands:
rm backend/services/retry_service.py
rm backend/tests/test_retry_service.py
```

### 6.6 Phase 6 Checklist

- [ ] Create `backend/tasks/__init__.py`
- [ ] Create `backend/tasks/broadcast_tasks.py` with all tasks
- [ ] Update `backend/services/broadcast_service.py` to queue tasks
- [ ] Update `backend/routers/whatsapp.py` with confirmation handler
- [ ] Update status callback to handle broadcast messages
- [ ] **DELETE** `backend/services/retry_service.py`
- [ ] **DELETE** `backend/tests/test_retry_service.py`
- [ ] Test `process_broadcast` task manually
- [ ] Test `send_actual_message` task manually
- [ ] Verify retry task in Celery beat logs

**Success Criteria:**
- ✅ Broadcast queues successfully when API called
- ✅ Template messages sent in batches of 50
- ✅ Confirmation button triggers actual message sending
- ✅ Status callbacks update broadcast contact status
- ✅ Retry task runs every 5 minutes
- ✅ Only FAILED/UNDELIVERED messages are retried
- ✅ Old retry service files deleted

---

## Phase 7: Integration Tests & Operations Guide

### 7.1 Integration Tests

**File: `backend/tests/test_broadcast_integration.py`** (NEW)

```python
"""
Integration tests for broadcast API with Celery tasks.
Tests end-to-end flow: create → send → confirm → deliver.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.broadcast import (
    BroadcastMessage,
    BroadcastRecipient,
)
from models.message import Message, MessageType, DeliveryStatus
from models.customer import Customer
from tasks.broadcast_tasks import (
    process_broadcast,
    send_actual_message,
    retry_failed_broadcasts,
)


@pytest.fixture
def mock_whatsapp_service():
    """Mock WhatsAppService for testing."""
    with patch("tasks.broadcast_tasks.WhatsAppService") as mock:
        instance = MagicMock()
        instance.send_template_message.return_value = {
            "sid": "SM_test_template_123",
            "status": "queued",
        }
        instance.send_message.return_value = {
            "sid": "SM_test_message_456",
            "status": "queued",
        }
        mock.return_value = instance
        yield instance


def test_broadcast_end_to_end_flow(
    client: TestClient,
    db: Session,
    admin_user_token: str,
    broadcast_group,
    customers,
    mock_whatsapp_service,
):
    """
    Test complete broadcast flow:
    1. Create broadcast
    2. Queue processing (Celery task)
    3. Template sent to all contacts
    4. User confirms (webhook)
    5. Actual message sent
    6. Status callback updates delivery status
    """
    # Step 1: Create broadcast message
    response = client.post(
        "/api/broadcast/messages",
        headers={"Authorization": f"Bearer {admin_user_token}"},
        json={
            "group_ids": [broadcast_group.id],
            "message": "Important agricultural update",
        },
    )
    assert response.status_code == 201
    data = response.json()
    broadcast_id = data["id"]

    # Verify broadcast created with contacts
    broadcast = (
        db.query(BroadcastMessage)
        .filter(BroadcastMessage.id == broadcast_id)
        .first()
    )
    assert broadcast is not None
    assert len(broadcast.broadcast_recipients) == len(customers)

    # Step 2: Process broadcast (Celery task)
    result = process_broadcast(broadcast_id)
    assert result["sent"] == len(customers)
    assert result["failed"] == 0

    # Verify template messages sent
    contacts = (
        db.query(BroadcastRecipient)
        .filter(BroadcastRecipient.broadcast_message_id == broadcast_id)
        .all()
    )
    for contact in contacts:
        assert contact.status == DeliveryStatus.SENT
        assert contact.template_message_sid is not None
        assert contact.sent_at is not None

    # Verify WhatsAppService.send_template_message called
    assert mock_whatsapp_service.send_template_message.call_count == len(
        customers
    )

    # Step 3: Simulate user confirmation (webhook)
    customer = customers[0]
    contact = contacts[0]

    response = client.post(
        "/whatsapp/webhook",
        data={
            "From": f"whatsapp:{customer.phone_number}",
            "Body": "Yes",
            "MessageSid": "SM_confirmation_123",
            "ButtonPayload": "read_broadcast",
        },
    )
    assert response.status_code == 200

    # Verify contact marked as confirmed (status remains SENT, confirmed_at is set)
    db.refresh(contact)
    assert contact.status == DeliveryStatus.SENT  # Status unchanged
    assert contact.confirmed_at is not None  # Confirmation timestamp set

    # Step 4: Send actual message (Celery task)
    result = send_actual_message(
        contact.id,
        customer.phone_number,
        broadcast.message,
    )
    assert result["status"] == "sent"

    # Verify actual message sent and Message record created
    db.refresh(contact)
    assert contact.actual_message_sid is not None
    assert contact.message_id is not None

    message = (
        db.query(Message)
        .filter(Message.id == contact.message_id)
        .first()
    )
    assert message is not None
    assert message.message_type == MessageType.BROADCAST
    assert message.body == broadcast.message

    # Verify WhatsAppService.send_message called with formatted message
    call_args = mock_whatsapp_service.send_message.call_args
    assert "[Broadcast]" in call_args[0][1]  # Message formatted

    # Step 5: Simulate delivery status callback
    response = client.post(
        "/whatsapp/status",
        data={
            "MessageSid": contact.actual_message_sid,
            "MessageStatus": "delivered",
            "To": f"whatsapp:{customer.phone_number}",
            "From": "whatsapp:+1234567890",
        },
    )
    assert response.status_code == 200

    # Verify contact status updated to delivered
    db.refresh(contact)
    assert contact.status == DeliveryStatus.DELIVERED
    assert contact.delivered_at is not None


def test_broadcast_batch_processing(
    db: Session,
    broadcast_message_with_100_contacts,
    mock_whatsapp_service,
):
    """
    Test batch processing with max 50 recipients per batch.
    Verify multiple batches processed correctly.
    """
    broadcast_id = broadcast_message_with_100_contacts.id

    # Process first batch
    result = process_broadcast(broadcast_id)
    assert result["sent"] == 50  # Max batch size
    assert result["remaining"] == 50

    # Verify task requeued for remaining contacts
    # (In real scenario, Celery would process this automatically)
    result = process_broadcast(broadcast_id)
    assert result["sent"] == 50
    assert result["remaining"] == 0

    # Verify all contacts processed
    all_contacts = (
        db.query(BroadcastRecipient)
        .filter(
            BroadcastRecipient.broadcast_message_id == broadcast_id,
            BroadcastRecipient.status == DeliveryStatus.SENT,
        )
        .count()
    )
    assert all_contacts == 100


def test_retry_failed_broadcasts(
    db: Session,
    failed_broadcast_recipients,
    mock_whatsapp_service,
):
    """
    Test retry mechanism for failed/undelivered messages.
    Verify only FAILED/UNDELIVERED retried, not SENT/DELIVERED.
    """
    # Setup: 5 failed contacts with different retry counts
    contacts = failed_broadcast_recipients
    contacts[0].status = DeliveryStatus.FAILED
    contacts[0].retry_count = 0
    contacts[0].sent_at = datetime.utcnow() - timedelta(minutes=6)

    contacts[1].status = DeliveryStatus.UNDELIVERED
    contacts[1].retry_count = 1
    contacts[1].sent_at = datetime.utcnow() - timedelta(minutes=16)

    contacts[2].status = DeliveryStatus.FAILED
    contacts[2].retry_count = 2
    contacts[2].sent_at = datetime.utcnow() - timedelta(minutes=61)

    contacts[3].status = DeliveryStatus.SENT  # Should NOT retry
    contacts[3].retry_count = 0

    contacts[4].status = DeliveryStatus.DELIVERED  # Should NOT retry
    contacts[4].retry_count = 0

    db.commit()

    # Run retry task
    retry_failed_broadcasts()

    # Verify only failed/undelivered retried
    db.refresh(contacts[0])
    assert contacts[0].retry_count == 1
    assert contacts[0].status == DeliveryStatus.SENT

    db.refresh(contacts[1])
    assert contacts[1].retry_count == 2

    db.refresh(contacts[2])
    assert contacts[2].retry_count == 3

    # Verify SENT and DELIVERED not retried
    db.refresh(contacts[3])
    assert contacts[3].retry_count == 0
    assert contacts[3].status == DeliveryStatus.SENT

    db.refresh(contacts[4])
    assert contacts[4].retry_count == 0
    assert contacts[4].status == DeliveryStatus.DELIVERED

    # Verify WhatsAppService called only 3 times (for failed/undelivered)
    assert mock_whatsapp_service.send_template_message.call_count == 3


def test_retry_max_attempts_reached(
    db: Session,
    failed_broadcast_contact,
    mock_whatsapp_service,
):
    """
    Test that contacts are marked permanently failed after max retries.
    Max retries: 3 (5min, 15min, 60min intervals).
    """
    contact = failed_broadcast_contact
    contact.status = DeliveryStatus.FAILED
    contact.retry_count = 2  # Already tried twice
    contact.sent_at = datetime.utcnow() - timedelta(minutes=61)
    db.commit()

    # Mock send_template_message to fail
    mock_whatsapp_service.send_template_message.side_effect = Exception(
        "Twilio error"
    )

    # Run retry task
    retry_failed_broadcasts()

    # Verify contact marked permanently failed
    db.refresh(contact)
    assert contact.retry_count == 3
    assert contact.status == DeliveryStatus.FAILED
    assert "Twilio error" in contact.error_message


def test_status_callback_updates_broadcast_contact(
    client: TestClient,
    db: Session,
    broadcast_contact,
):
    """
    Test Twilio status callback updates broadcast contact status.
    Tests delivered, failed, undelivered, and read statuses.
    """
    # Test delivered status
    response = client.post(
        "/whatsapp/status",
        data={
            "MessageSid": broadcast_contact.template_message_sid,
            "MessageStatus": "delivered",
            "To": f"whatsapp:{broadcast_contact.customer.phone_number}",
            "From": "whatsapp:+1234567890",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["broadcast_contact_id"] == broadcast_contact.id

    db.refresh(broadcast_contact)
    assert broadcast_contact.status == DeliveryStatus.DELIVERED
    assert broadcast_contact.delivered_at is not None

    # Test read status
    response = client.post(
        "/whatsapp/status",
        data={
            "MessageSid": broadcast_contact.template_message_sid,
            "MessageStatus": "read",
            "To": f"whatsapp:{broadcast_contact.customer.phone_number}",
            "From": "whatsapp:+1234567890",
        },
    )
    assert response.status_code == 200

    db.refresh(broadcast_contact)
    assert broadcast_contact.status == DeliveryStatus.READ
    assert broadcast_contact.read_at is not None
```

### 7.2 Test Fixtures

**File: `backend/tests/conftest.py`**

Add broadcast-specific fixtures:

```python
@pytest.fixture
def broadcast_message_with_100_contacts(
    db: Session, broadcast_group, admin_user
):
    """Create broadcast with 100 contacts for batch testing."""
    # Create 100 customers
    customers = []
    for i in range(100):
        customer = Customer(
            phone_number=f"+62812345{i:04d}",
            full_name=f"Test Customer {i}",
            administrative_id=broadcast_group.administrative_id,
        )
        db.add(customer)
        customers.append(customer)

    # Add to broadcast group
    for customer in customers:
        broadcast_group.customers.append(customer)

    # Create broadcast message
    broadcast = BroadcastMessage(
        message="Test broadcast with 100 contacts",
        created_by_id=admin_user.id,
        status="pending",
    )
    broadcast.broadcast_groups.append(broadcast_group)
    db.add(broadcast)
    db.commit()

    # Create broadcast contacts
    for customer in customers:
        contact = BroadcastRecipient(
            broadcast_message_id=broadcast.id,
            customer_id=customer.id,
            status=DeliveryStatus.PENDING,
        )
        db.add(contact)

    db.commit()
    db.refresh(broadcast)
    return broadcast


@pytest.fixture
def failed_broadcast_recipients(db: Session, broadcast_message):
    """Create 5 broadcast contacts with failed status."""
    contacts = []
    for i in range(5):
        customer = Customer(
            phone_number=f"+6281234500{i}",
            full_name=f"Failed Customer {i}",
        )
        db.add(customer)
        db.commit()

        contact = BroadcastRecipient(
            broadcast_message_id=broadcast_message.id,
            customer_id=customer.id,
            status=DeliveryStatus.FAILED,
            retry_count=0,
        )
        db.add(contact)
        contacts.append(contact)

    db.commit()
    return contacts


@pytest.fixture
def failed_broadcast_contact(db: Session, broadcast_message, customer):
    """Single failed broadcast contact."""
    contact = BroadcastRecipient(
        broadcast_message_id=broadcast_message.id,
        customer_id=customer.id,
        status=DeliveryStatus.FAILED,
        retry_count=0,
        template_message_sid="SM_failed_123",
    )
    db.add(contact)
    db.commit()
    return contact
```

### 7.3 Manual Testing Guide

**File: `docs/BROADCAST_API_TESTING_GUIDE.md`** (NEW)

```markdown
# Broadcast API Testing Guide

## Prerequisites

1. Start all services:
   ```bash
   ./dc.sh up -d
   ```

2. Verify services running:
   ```bash
   ./dc.sh ps
   # Should show: backend, redis, celery-worker, celery-beat
   ```

3. Check Celery worker logs:
   ```bash
   ./dc.sh logs celery-worker -f
   ```

## Manual Testing Steps

### 1. Create Broadcast Group

```bash
curl -X POST http://localhost:8000/api/broadcast/groups \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Farmers",
    "description": "Test broadcast group",
    "customer_ids": [1, 2, 3]
  }'
```

### 2. Send Broadcast Message

```bash
curl -X POST http://localhost:8000/api/broadcast/messages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "group_ids": [1],
    "message": "Important: New fertilizer subsidy available"
  }'
```

Expected response:
```json
{
  "id": 1,
  "message": "Important: New fertilizer subsidy available",
  "status": "processing",
  "queued_at": "2025-01-15T10:00:00Z",
  "total_contacts": 3,
  "sent_count": 0
}
```

### 3. Monitor Celery Worker Logs

```bash
./dc.sh logs celery-worker -f
```

You should see:
```
[INFO] Processing broadcast 1 for 3 contacts
[INFO] Template sent to +6281234567890: SM_xxx
[INFO] Template sent to +6281234567891: SM_yyy
[INFO] Template sent to +6281234567892: SM_zzz
```

### 4. Check Broadcast Status

```bash
curl http://localhost:8000/api/broadcast/messages/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Expected response:
```json
{
  "id": 1,
  "message": "Important: New fertilizer subsidy available",
  "status": "processing",
  "total_contacts": 3,
  "sent_count": 3,
  "delivered_count": 0,
  "failed_count": 0,
  "contacts": [
    {
      "customer_id": 1,
      "customer_phone": "+6281234567890",
      "status": "sent",
      "sent_at": "2025-01-15T10:00:05Z"
    }
  ]
}
```

### 5. Simulate User Confirmation (Webhook)

Recipient clicks "Yes" button in WhatsApp:

```bash
curl -X POST http://localhost:8000/whatsapp/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+6281234567890" \
  -d "Body=Yes" \
  -d "MessageSid=SM_confirm_123" \
  -d "ButtonPayload=read_broadcast"
```

Expected: Actual message sent via Celery task

### 6. Simulate Status Callback (Twilio)

```bash
curl -X POST http://localhost:8000/whatsapp/status \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "MessageSid=SM_xxx" \
  -d "MessageStatus=delivered" \
  -d "To=whatsapp:+6281234567890" \
  -d "From=whatsapp:+1234567890"
```

Expected response:
```json
{
  "status": "success",
  "message": "Broadcast status updated",
  "broadcast_contact_id": 1
}
```

### 7. Test Retry Logic

Manually mark contact as failed:

```sql
UPDATE broadcast_recipients
SET status = 'failed',
    sent_at = NOW() - INTERVAL '6 minutes',
    retry_count = 0
WHERE id = 1;
```

Wait for Celery beat task (runs every 5 minutes):

```bash
./dc.sh logs celery-beat -f
```

Should see:
```
[INFO] Retrying 1 contacts at retry attempt 1 (after 5min)
[INFO] Retry successful for contact 1: SM_retry_xxx
```

## Testing Checklist

- [ ] Broadcast group created successfully
- [ ] Broadcast message queued and processed
- [ ] Template messages sent in batches (max 50)
- [ ] Confirmation button triggers actual message
- [ ] Status callbacks update contact status
- [ ] Retry task runs every 5 minutes
- [ ] Only FAILED/UNDELIVERED messages retried
- [ ] Message appears in history with BROADCAST type
- [ ] EO can view delivery status per contact

## Common Issues

**Issue: Celery worker not processing tasks**
- Check Redis connection: `./dc.sh exec redis redis-cli ping`
- Restart worker: `./dc.sh restart celery-worker`

**Issue: Template message fails**
- Verify `BROADCAST_TEMPLATE_SID` in `.env`
- Check Twilio credentials

**Issue: Retry not working**
- Check Celery beat logs: `./dc.sh logs celery-beat`
- Verify contact status is FAILED or UNDELIVERED (not SENT/DELIVERED)
```

### 7.4 Operations Guide

**File: `docs/BROADCAST_API_OPERATIONS.md`** (NEW)

```markdown
# Broadcast API Operations Guide

## Monitoring

### Check Celery Worker Health

```bash
./dc.sh exec celery-worker celery -A celery_app inspect active
```

### Check Celery Beat Schedule

```bash
./dc.sh exec celery-beat celery -A celery_app inspect scheduled
```

### Monitor Redis Queue

```bash
./dc.sh exec redis redis-cli
> LLEN celery
> KEYS *
```

### Check Broadcast Status

```sql
-- Pending broadcasts
SELECT id, message, status, queued_at, created_at
FROM broadcast_messages
WHERE status = 'processing';

-- Failed contacts needing retry
SELECT
  bc.id,
  bc.customer_id,
  bc.status,
  bc.retry_count,
  bc.error_message,
  bc.sent_at
FROM broadcast_recipients bc
WHERE bc.status IN ('failed', 'undelivered')
AND bc.retry_count < 3
ORDER BY bc.sent_at;
```

## Scaling

### Increase Worker Instances

```yaml
# docker-compose.yml
celery-worker:
  deploy:
    replicas: 3  # Run 3 workers
```

### Adjust Batch Size

```python
# config.py
broadcast_batch_size: int = 100  # Increase from 50
```

### Adjust Retry Intervals

```python
# config.py
broadcast_retry_intervals: List[int] = [5, 15, 30, 60]  # Add 30min
```

## Troubleshooting

### Worker Memory Issues

```bash
# Restart worker after fewer tasks
# celery_app.py
worker_max_tasks_per_child = 500  # Reduce from 1000
```

### Task Timeout Issues

```bash
# Increase task timeout
# celery_app.py
task_time_limit = 600  # 10 minutes
task_soft_time_limit = 540  # 9 minutes
```

### Redis Memory Full

```bash
# Check Redis memory
./dc.sh exec redis redis-cli INFO memory

# Increase Redis memory limit
# docker-compose.yml
redis:
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

## Maintenance

### Clear Failed Tasks

```sql
-- Reset contacts stuck in failed status
UPDATE broadcast_recipients
SET status = 'pending', retry_count = 0, error_message = NULL
WHERE status = 'failed' AND retry_count >= 3;
```

### Archive Old Broadcasts

```sql
-- Archive broadcasts older than 30 days
UPDATE broadcast_messages
SET status = 'archived'
WHERE created_at < NOW() - INTERVAL '30 days';
```

### Purge Celery Queue

```bash
./dc.sh exec celery-worker celery -A celery_app purge
```
```

### 7.5 Phase 7 Checklist

- [ ] Create `backend/tests/test_broadcast_integration.py`
- [ ] Add broadcast fixtures to `conftest.py`
- [ ] Create `docs/BROADCAST_API_TESTING_GUIDE.md`
- [ ] Create `docs/BROADCAST_API_OPERATIONS.md`
- [ ] Run all integration tests: `pytest tests/test_broadcast_integration.py -v`
- [ ] Perform manual testing using testing guide
- [ ] Test retry logic with failed messages
- [ ] Test batch processing with 100+ contacts
- [ ] Document any issues found

**Success Criteria:**
- ✅ All integration tests pass
- ✅ Manual testing completed successfully
- ✅ Retry logic works as expected
- ✅ Operations guide covers monitoring and troubleshooting
- ✅ Testing guide covers all scenarios

---

## Implementation Checklist (Plan 2)

### Phase 5: Celery Setup
- [ ] Add Celery/Redis dependencies
- [ ] Create celery_app.py
- [ ] Update config.py
- [ ] Update docker-compose.yml
- [ ] Test all services start

### Phase 6: Broadcast Tasks & Integration
- [ ] Create broadcast_tasks.py
- [ ] Update broadcast_service.py
- [ ] Update whatsapp.py webhook
- [ ] Update status callback
- [ ] **DELETE retry_service.py**
- [ ] **DELETE test_retry_service.py**
- [ ] Test end-to-end flow

### Phase 7: Tests & Documentation
- [ ] Create integration tests
- [ ] Add test fixtures
- [ ] Create testing guide
- [ ] Create operations guide
- [ ] Run full test suite

---

## Success Criteria (Overall)

### Functional Requirements
- ✅ Broadcasts queue via Celery with Redis broker
- ✅ Template messages sent in batches (max 50)
- ✅ Users confirm via button, actual message sent
- ✅ Status callbacks update delivery status in real-time
- ✅ Only FAILED/UNDELIVERED messages retried
- ✅ Exponential backoff: 5min, 15min, 60min
- ✅ Broadcast messages appear in history as BROADCAST type
- ✅ EO can view per-contact delivery status

### Technical Requirements
- ✅ Uses existing `WhatsAppService.send_template_message()`
- ✅ Old retry_service.py deleted
- ✅ Celery worker, beat, Redis services running
- ✅ Webhook handlers for confirmation and status
- ✅ Integration tests cover all scenarios
- ✅ Operations guide for monitoring and scaling

### Performance
- ✅ Processes 50 messages per batch
- ✅ Handles 1000+ recipients efficiently
- ✅ Retry task runs every 5 minutes
- ✅ No memory leaks in workers

---

## Notes

1. **Celery vs Direct Processing**: Using Celery provides:
   - Asynchronous processing (API responds immediately)
   - Reliable queue (Redis persistence)
   - Scalable workers (can add more instances)
   - Built-in retry mechanisms
   - Scheduled tasks via Celery Beat

2. **Two-Step Delivery**: Required by user specification:
   - Step 1: Template with confirmation button
   - Step 2: Actual message after confirmation
   - Pattern from rag-doll: `[Broadcast]` prefix in messages

3. **Retry Logic**: Only FAILED/UNDELIVERED:
   - SENT → Not retried (still in transit)
   - DELIVERED → Not retried (successfully delivered)
   - FAILED → Retry with exponential backoff
   - UNDELIVERED → Retry with exponential backoff

4. **Status Tracking**: Real-time via webhooks:
   - Template status → Updates broadcast_contact
   - Actual message status → Updates broadcast_contact + message
   - Read receipts → Updates read_at timestamp

5. **Batch Processing**: Prevents rate limiting:
   - Max 50 recipients per batch
   - 2 second delay between batches
   - Automatic requeuing for remaining contacts
