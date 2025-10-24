import os

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.customer import AgeGroup

# Set testing environment
os.environ["TESTING"] = "true"

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

    age_group_enum.create(engine, checkfirst=True)

    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)

    # Drop enum types
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

        # Delete in correct order to respect foreign key constraints
        db.query(UserAdministrative).delete()
        db.query(CustomerAdministrative).delete()
        db.query(Ticket).delete()
        db.query(Message).delete()
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

        def notify_ticket_resolved(self, *args, **kwargs):
            pass

        def notify_message_status(self, *args, **kwargs):
            pass

    # Mock WhatsAppService to prevent actual API calls
    class MockWhatsAppService:
        def __init__(self, *args, **kwargs):
            pass

        def send_confirmation_template(self, *args, **kwargs):
            return {"sid": "mock_message_sid"}

        def send_message(self, *args, **kwargs):
            return {"sid": "mock_message_sid"}

    # Mock EmailService to prevent actual email sending
    class MockEmailService:
        def __init__(self, *args, **kwargs):
            pass

        async def send_invitation_email(self, *args, **kwargs):
            return True

        async def send_password_reset_email(self, *args, **kwargs):
            return True

    monkeypatch.setattr("routers.messages.emit_message_created", mock_emit)
    monkeypatch.setattr(
        "routers.messages.emit_message_status_updated", mock_emit
    )
    monkeypatch.setattr("routers.messages.emit_ticket_resolved", mock_emit)
    monkeypatch.setattr("routers.tickets.emit_ticket_created", mock_emit)
    monkeypatch.setattr("routers.callbacks.emit_whisper_created", mock_emit)
    monkeypatch.setattr(
        "routers.ws.PushNotificationService",
        MockPushNotificationService
    )
    monkeypatch.setattr(
        "routers.callbacks.WhatsAppService",
        MockWhatsAppService
    )
    # Mock the email_service instance (not EmailService class)
    monkeypatch.setattr(
        "services.user_service.email_service",
        MockEmailService()
    )


@pytest.fixture
def mock_akvo_rag_client(monkeypatch):
    """Mock httpx client for akvo-rag service tests"""
    from unittest.mock import AsyncMock, MagicMock

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client, mock_response
