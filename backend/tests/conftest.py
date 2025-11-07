"""
Test Configuration and Fixtures

CRITICAL SECURITY: This file implements defense-in-depth mocking to prevent
real API calls (WhatsApp/Twilio, Email, Push Notifications) during testing.

## Mocking Strategy

### 1. Environment-Based Mocking (Primary Defense)
   - Sets TESTING=true environment variable
   - WhatsAppService checks this in __init__ and creates mock client
   - Prevents accidental real API calls even if patching fails

### 2. Patch-Based Mocking (Secondary Defense)
   - Patches WhatsAppService in ALL routers (callbacks, messages, whatsapp)
   - Provides MockWhatsAppService with all required methods
   - Ensures consistent mock behavior across all tests

### 3. Service-Level Mocking (Tertiary Defense)
   - Mocks PushNotificationService to prevent push notifications
   - Mocks EmailService to prevent email sending
   - Mocks WebSocket emitters to prevent real-time events

## Why Defense-in-Depth?
   - Tests must NEVER trigger real API calls
   - Real API calls can:
     * Cost money (Twilio charges per message)
     * Send messages to real phone numbers
     * Leak test data to production systems
   - Multiple layers ensure safety even if one layer fails

## Adding New External Services
   When adding new external services:
   1. Add TESTING environment check in service __init__
   2. Create mock class in this file
   3. Patch service in ALL locations where it's imported
   4. Add tests to verify mocking works

## Testing the Mocking
   Run: pytest tests/test_whatsapp_service.py -v
   Run: pytest tests/test_customer_endpoints.py -v
   Run: pytest tests/test_callbacks.py -v

   All should pass with NO real API calls.
"""

import os

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.customer import AgeGroup, OnboardingStatus
from models.message import DeliveryStatus

# CRITICAL: Set testing environment to prevent real API calls
# This is the PRIMARY defense against real Twilio/WhatsApp/Email API calls
# Set both TESTING and TEST for backward compatibility with different services
os.environ["TESTING"] = "true"  # Used by WhatsAppService
os.environ["TEST"] = "true"  # Used by EmailService

# Test database URL
TEST_DATABASE_URL = "postgresql://akvo:password@db:5432/agriconnect_test"

# Create test engine
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


@pytest.fixture(scope="session")
def test_db():
    # Create enum types before creating tables
    age_group_enum = sa.Enum(AgeGroup, name="agegroup")
    delivery_status_enum = sa.Enum(DeliveryStatus, name="deliverystatus")
    onboarding_status_enum = sa.Enum(OnboardingStatus, name="onboardingstatus")

    age_group_enum.create(engine, checkfirst=True)
    delivery_status_enum.create(engine, checkfirst=True)
    onboarding_status_enum.create(engine, checkfirst=True)

    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)

    # Drop enum types
    onboarding_status_enum.drop(engine, checkfirst=True)
    delivery_status_enum.drop(engine, checkfirst=True)
    age_group_enum.drop(engine, checkfirst=True)


@pytest.fixture
def db_session(test_db):
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        # Clean up all tables after each test
        from models import (
            Administrative,
            AdministrativeLevel,
            Customer,
            CustomerAdministrative,
            Device,
            KnowledgeBase,
            Message,
            ServiceToken,
            User,
            UserAdministrative,
        )

        # Import Ticket model
        from models.ticket import Ticket

        # Import PlaygroundMessage model
        from models.playground_message import PlaygroundMessage

        # Import Broadcast models
        from models.broadcast import (
            BroadcastRecipient,
            BroadcastMessageGroup,
            BroadcastMessage,
            BroadcastGroupContact,
            BroadcastGroup,
        )

        # Delete in correct order to respect foreign key constraints
        db.query(UserAdministrative).delete()
        db.query(CustomerAdministrative).delete()
        db.query(Ticket).delete()
        db.query(Message).delete()
        db.query(PlaygroundMessage).delete()  # Playground messages
        # Broadcast tables must be deleted before Customer and Administrative
        db.query(BroadcastRecipient).delete()
        db.query(BroadcastMessageGroup).delete()
        db.query(BroadcastMessage).delete()
        db.query(BroadcastGroupContact).delete()
        db.query(BroadcastGroup).delete()
        db.query(Customer).delete()
        db.query(KnowledgeBase).delete()
        # Device must be deleted before Administrative (foreign key)
        db.query(Device).delete()
        db.query(Administrative).delete()
        db.query(AdministrativeLevel).delete()
        db.query(ServiceToken).delete()
        db.query(User).delete()
        db.commit()
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers_factory(db_session):
    """Factory fixture to create auth headers for admin or EO users."""
    from models.user import User, UserType
    from models.administrative import UserAdministrative
    from utils.auth import create_access_token

    def _create_auth_headers(
        user_type: str = "eo",
        email: str = None,
        administrative_ids: list = None,
        **user_kwargs,
    ) -> tuple[dict, User]:
        """
        Create authentication headers for testing.

        Args:
            user_type: 'admin' or 'eo' (extension officer)
            email: Optional custom email (auto-generated if not provided)
            administrative_ids: List of administrative IDs to assign to
            EO users
            **user_kwargs: Additional user attributes
                (full_name, phone_number, etc.)

        Returns:
            tuple: (auth_headers dict, user object)
        """
        # Set defaults based on user type
        if user_type == "admin":
            email = email or "admin@example.com"
            phone = user_kwargs.get("phone_number", "+10000000001")
            full_name = user_kwargs.get("full_name", "Admin User")
            user_type_enum = UserType.ADMIN
        else:
            email = email or "eo@example.com"
            phone = user_kwargs.get("phone_number", "+10000000002")
            full_name = user_kwargs.get("full_name", "Extension Officer")
            user_type_enum = UserType.EXTENSION_OFFICER

        # Create user
        user = User(
            email=email,
            phone_number=phone,
            full_name=full_name,
            user_type=user_type_enum,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Assign administrative areas to EO users
        if user_type_enum == UserType.EXTENSION_OFFICER and administrative_ids:
            for admin_id in administrative_ids:
                user_admin = UserAdministrative(
                    user_id=user.id, administrative_id=admin_id
                )
                db_session.add(user_admin)
            db_session.commit()

        # Generate JWT token
        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}, user

    return _create_auth_headers


@pytest.fixture(autouse=True)
def mock_websocket_emitters(monkeypatch):
    """Mock WebSocket emitters and push notifications for all tests."""

    async def mock_emit(*args, **kwargs):
        pass

    # Mock a push notification service that does nothing
    class MockPushNotificationService:
        def __init__(self, *args, **kwargs):
            pass

        def notify_new_ticket(self, *args, **kwargs):
            pass

        def notify_new_message(self, *args, **kwargs):
            pass

        def notify_ticket_resolved(self, *args, **kwargs):
            pass

        def notify_message_status(self, *args, **kwargs):
            pass

    # Mock WhatsAppService to prevent actual API calls
    # CRITICAL: This mock prevents ANY real WhatsApp/Twilio API calls
    # during testing, regardless of environment configuration
    class MockWhatsAppService:
        def __init__(self, *args, **kwargs):
            self.testing_mode = True  # Always in test mode
            import uuid

            self._uuid = uuid  # Store for use in methods

        def _generate_unique_sid(self):
            """Generate unique SID to prevent DB constraint violations"""
            return f"MOCK_SID_{self._uuid.uuid4().hex[:12].upper()}"

        def send_confirmation_template(self, *args, **kwargs):
            return {"sid": self._generate_unique_sid(), "status": "sent"}

        def send_message(self, *args, **kwargs):
            return {"sid": self._generate_unique_sid(), "status": "sent"}

        def send_template_message(self, *args, **kwargs):
            return {"sid": self._generate_unique_sid(), "status": "sent"}

        def send_welcome_message(self, *args, **kwargs):
            return {"sid": self._generate_unique_sid(), "status": "sent"}

    # Mock EmailService to prevent actual email sending
    class MockEmailService:
        def __init__(self, *args, **kwargs):
            pass

        async def send_invitation_email(self, *args, **kwargs):
            return True

        async def send_password_reset_email(self, *args, **kwargs):
            return True

    # Mock emit functions from services.socketio_service (new location)
    monkeypatch.setattr(
        "services.socketio_service.emit_message_received", mock_emit
    )
    monkeypatch.setattr(
        "services.socketio_service.emit_playground_response", mock_emit
    )
    monkeypatch.setattr(
        "services.socketio_service.emit_whisper_created", mock_emit
    )
    monkeypatch.setattr(
        "services.socketio_service.emit_ticket_resolved", mock_emit
    )
    monkeypatch.setattr(
        "services.socketio_service.PushNotificationService",
        MockPushNotificationService
    )

    # CRITICAL: Patch WhatsAppService in ALL routers to prevent real API calls
    # This is defense-in-depth: even if TESTING env var isn't set,
    # these mocks ensure no real messages are sent during tests
    monkeypatch.setattr(
        "routers.callbacks.WhatsAppService", MockWhatsAppService
    )
    monkeypatch.setattr(
        "routers.messages.WhatsAppService", MockWhatsAppService
    )
    monkeypatch.setattr(
        "routers.whatsapp.WhatsAppService", MockWhatsAppService
    )

    # Mock the email_service instance (not EmailService class)
    monkeypatch.setattr(
        "services.user_service.email_service", MockEmailService()
    )
