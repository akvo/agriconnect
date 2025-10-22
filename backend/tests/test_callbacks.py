import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.administrative import Administrative, AdministrativeLevel
from services.service_token_service import ServiceTokenService


@pytest.fixture
def service_token_and_plain(db_session: Session):
    """Create a service token for testing"""
    service_token, plain_token = ServiceTokenService.create_token(
        db_session, "akvo-rag", "callback:write"
    )
    return service_token, plain_token


@pytest.fixture
def test_customer(db_session: Session):
    """Create a test customer"""
    customer = Customer(
        phone_number="+1234567890", language=CustomerLanguage.EN
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_message(db_session: Session, test_customer):
    """Create a test message from customer"""
    message = Message(
        message_sid="test_msg_123",
        customer_id=test_customer.id,
        user_id=None,
        body="Hello, I need help with water treatment",
        from_source=MessageFrom.CUSTOMER,
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


def test_ai_callback_success(
    client: TestClient, service_token_and_plain, db_session: Session
):
    """Test successful AI callback"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_123",
        "stage": "done",
        "result": {
            "answer": "Use 2-4 mg/L free chlorine for water treatment",
            "citations": [
                {"title": "WHO Water Quality", "url": "https://who.int/water"}
            ],
        },
        "callback_params": {
            "message_id": 123,
            "message_type": 1,
        },
        "trace_id": "trace_001",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_123"}


def test_ai_callback_success_with_message_storage(
    client: TestClient,
    service_token_and_plain,
    test_message,
    db_session: Session,
):
    """Test successful AI callback that stores response in database"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_456",
        "stage": "done",
        "result": {
            "answer": "Use 2-4 mg/L free chlorine for water treatment",
            "citations": [
                {"title": "WHO Water Quality", "url": "https://who.int/water"}
            ],
        },
        "callback_params": {
            "message_id": test_message.id,  # Use real message ID
            "message_type": 2,  # Test WHISPER type
        },
        "trace_id": "trace_002",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_456"}

    # Verify AI response was stored in database
    ai_messages = (
        db_session.query(Message)
        .filter(Message.from_source == MessageFrom.LLM)
        .filter(Message.customer_id == test_message.customer_id)
        .all()
    )

    assert len(ai_messages) == 1
    ai_message = ai_messages[0]
    assert ai_message.body == "Use 2-4 mg/L free chlorine for water treatment"
    assert ai_message.message_sid == "ai_job_456"
    assert ai_message.customer_id == test_message.customer_id
    assert ai_message.from_source == MessageFrom.LLM
    # Import MessageType to check the value
    from schemas.callback import MessageType
    assert ai_message.message_type == MessageType.WHISPER


def test_ai_callback_success_invalid_message_id(
    client: TestClient, service_token_and_plain, db_session: Session
):
    """Test AI callback with invalid message_id - should not store response"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_invalid",
        "stage": "done",
        "result": {
            "answer": "Use 2-4 mg/L free chlorine for water treatment",
            "citations": [
                {"title": "WHO Water Quality", "url": "https://who.int/water"}
            ],
        },
        "callback_params": {
            "message_id": 99999,  # Non-existent message ID
            "message_type": 1,
        },
        "trace_id": "trace_invalid",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    # Should still return success (callback received)
    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_invalid"}

    # Verify no AI message was created
    ai_messages = (
        db_session.query(Message)
        .filter(Message.from_source == MessageFrom.LLM)
        .filter(Message.message_sid == "ai_job_invalid")
        .all()
    )

    assert len(ai_messages) == 0


def test_ai_callback_failed_job(
    client: TestClient, service_token_and_plain, db_session: Session
):
    """Test AI callback for failed job"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_456",
        "stage": "failed",
        "callback_params": {
            "message_id": 456,
            "message_type": 1,
        },
        "trace_id": "trace_002",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_456"}


def test_kb_callback_success(
    client: TestClient, service_token_and_plain, db_session: Session
):
    """Test successful KB callback"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "kb_job_789",
        "stage": "done",
        "callback_params": {"kb_id": 2, "user_id": 1},
        "trace_id": "trace_003",
        "job": "upload",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/kb", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "kb_job_789"}


def test_kb_callback_timeout(
    client: TestClient, service_token_and_plain, db_session: Session
):
    """Test KB callback for timeout"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "kb_job_timeout",
        "stage": "timeout",
        "trace_id": "trace_004",
        "job": "upload",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/kb", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "job_id": "kb_job_timeout",
    }


def test_callback_invalid_token(client: TestClient):
    """Test callback with invalid token"""
    payload = {
        "job_id": "job_123",
        "stage": "done",
        "event_type": "result",
        "job": "chat",
    }

    headers = {"Authorization": "Bearer invalid_token"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid service token"}


def test_callback_missing_token(client: TestClient):
    """Test callback without authorization header"""
    payload = {
        "job_id": "job_123",
        "stage": "done",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 403
    assert "Not authenticated" in response.json()["detail"]


def test_callback_invalid_stage_enum(
    client: TestClient, service_token_and_plain
):
    """Test callback with invalid stage enum"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_123",
        "stage": "invalid_stage",  # Invalid enum value
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 422  # Validation error


def test_callback_invalid_job_enum(
    client: TestClient, service_token_and_plain
):
    """Test callback with invalid job enum"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_123",
        "stage": "done",
        "job": "invalid_job",  # Invalid enum value
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 422  # Validation error


def test_callback_missing_required_fields(
    client: TestClient, service_token_and_plain
):
    """Test callback with missing required fields"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_123",
        # Missing stage, job
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 422  # Validation error


def test_callback_with_all_optional_fields(
    client: TestClient, service_token_and_plain
):
    """Test callback with all optional fields included"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_complete",
        "stage": "done",
        "result": {
            "answer": "Complete answer with citations",
            "citations": [
                {"title": "Source 1", "url": "https://example.com/1"},
                {"title": "Source 2", "url": "https://example.com/2"},
            ],
        },
        "callback_params": {
            "message_id": 789,
            "message_type": 1,
        },
        "trace_id": "trace_complete",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_complete"}


def test_callback_queued_stage(client: TestClient, service_token_and_plain):
    """Test callback with queued stage"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_queued",
        "stage": "queued",
        "job": "chat",
        "trace_id": "trace_queued",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_queued"}


@pytest.fixture
def test_administrative(db_session: Session):
    """Create a test administrative area"""
    # Create administrative level first
    level = AdministrativeLevel(name="District")
    db_session.add(level)
    db_session.commit()
    db_session.refresh(level)

    # Create administrative area
    admin = Administrative(
        code="TST001",
        name="Test District",
        level_id=level.id,
        path="/TST001",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def test_customer_with_ticket(db_session: Session, test_administrative):
    """Create a test customer with an open ticket"""
    from models.administrative import CustomerAdministrative

    customer = Customer(
        phone_number="+255987654321",
        language=CustomerLanguage.EN,
        full_name="Ticket Customer",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    # Link customer to administrative area
    customer_admin = CustomerAdministrative(
        customer_id=customer.id,
        administrative_id=test_administrative.id,
    )
    db_session.add(customer_admin)
    db_session.commit()

    # Create initial message
    message = Message(
        message_sid="ticket_msg_001",
        customer_id=customer.id,
        body="I need help with rice farming",
        from_source=MessageFrom.CUSTOMER,
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    # Create ticket
    ticket = Ticket(
        ticket_number="20251022TEST",
        customer_id=customer.id,
        administrative_id=test_administrative.id,
        message_id=message.id,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    return customer, ticket, message


def test_ai_callback_whisper_type_with_ticket_id(
    client: TestClient,
    service_token_and_plain,
    test_customer_with_ticket,
    db_session: Session,
):
    """Test AI callback with WHISPER type and explicit ticket_id"""
    _, plain_token = service_token_and_plain
    customer, ticket, message = test_customer_with_ticket

    payload = {
        "job_id": "whisper_job_001",
        "stage": "done",
        "result": {
            "answer": "Plant rice in well-drained soil with sunlight.",
            "citations": [
                {
                    "title": "Rice Growing Guide",
                    "url": "https://example.com/rice"
                }
            ],
        },
        "callback_params": {
            "message_id": message.id,
            "message_type": 2,  # WHISPER
            "ticket_id": ticket.id,
        },
        "trace_id": "trace_whisper_001",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post(
        "/api/callback/ai", json=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "job_id": "whisper_job_001"
    }

    # Verify whisper message was created
    whisper_messages = (
        db_session.query(Message)
        .filter(Message.from_source == MessageFrom.LLM)
        .filter(Message.customer_id == customer.id)
        .all()
    )

    assert len(whisper_messages) == 1
    whisper_msg = whisper_messages[0]
    assert whisper_msg.body == "Plant rice in well-drained soil with sunlight."  # noqa: E501
    assert whisper_msg.message_sid == "ai_whisper_job_001"
    assert whisper_msg.from_source == MessageFrom.LLM
    # Import MessageType to check the value
    from schemas.callback import MessageType
    assert whisper_msg.message_type == MessageType.WHISPER


def test_ai_callback_whisper_type_without_ticket_id(
    client: TestClient,
    service_token_and_plain,
    test_customer_with_ticket,
    db_session: Session,
):
    """Test AI callback with WHISPER type, ticket_id found from customer"""
    _, plain_token = service_token_and_plain
    customer, ticket, message = test_customer_with_ticket

    payload = {
        "job_id": "whisper_job_002",
        "stage": "done",
        "result": {
            "answer": "Use nitrogen-rich fertilizers for rice.",
            "citations": [
                {
                    "title": "Rice Fertilizer Guide",
                    "url": "https://example.com/rice-fert"
                }
            ],
        },
        "callback_params": {
            "message_id": message.id,
            "message_type": 2,  # WHISPER
            # No ticket_id provided - should find from customer
        },
        "trace_id": "trace_whisper_002",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post(
        "/api/callback/ai", json=payload, headers=headers
    )

    assert response.status_code == 200

    # Verify whisper message was created
    whisper_messages = (
        db_session.query(Message)
        .filter(Message.from_source == MessageFrom.LLM)
        .filter(Message.message_sid == "ai_whisper_job_002")
        .all()
    )

    assert len(whisper_messages) == 1
    whisper_msg = whisper_messages[0]
    assert whisper_msg.body == "Use nitrogen-rich fertilizers for rice."
    assert whisper_msg.customer_id == customer.id


def test_ai_callback_whisper_type_no_open_ticket(
    client: TestClient,
    service_token_and_plain,
    test_customer_with_ticket,
    db_session: Session,
):
    """Test AI callback with WHISPER type when ticket is resolved"""
    from datetime import datetime, timezone

    _, plain_token = service_token_and_plain
    customer, ticket, message = test_customer_with_ticket

    # Resolve the ticket
    ticket.resolved_at = datetime.now(timezone.utc)
    db_session.commit()

    payload = {
        "job_id": "whisper_job_003",
        "stage": "done",
        "result": {
            "answer": "This suggestion won't be sent anywhere.",
            "citations": [],
        },
        "callback_params": {
            "message_id": message.id,
            "message_type": 2,  # WHISPER
            # No ticket_id - should try to find open ticket but fail
        },
        "trace_id": "trace_whisper_003",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post(
        "/api/callback/ai", json=payload, headers=headers
    )

    assert response.status_code == 200

    # Verify whisper message was created
    whisper_messages = (
        db_session.query(Message)
        .filter(Message.from_source == MessageFrom.LLM)
        .filter(Message.message_sid == "ai_whisper_job_003")
        .all()
    )

    assert len(whisper_messages) == 1

    # emit_whisper_created should NOT be called (no open ticket)
    # This is handled by the global mock in conftest.py
