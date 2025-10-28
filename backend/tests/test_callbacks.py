import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.administrative import Administrative, AdministrativeLevel


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


def test_ai_callback_success(client: TestClient, db_session: Session):
    """Test successful AI callback"""
    payload = {
        "job_id": "job_123",
        "status": "completed",
        "output": {
            "answer": "Use 2-4 mg/L free chlorine for water treatment",
            "citations": [
                {
                    "document": "WHO Water Quality",
                    "chunk": (
                        "Free chlorine should be maintained at 2-4 mg/L"
                    ),
                    "page": "5",
                }
            ],
        },
        "error": None,
        "callback_params": (
            '{"message_id": 123, "message_type": 1, "customer_id": 100}'
        ),
        "trace_id": "trace_001",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_123"}


def test_ai_callback_success_with_message_storage(
    client: TestClient,
    test_message,
    db_session: Session,
):
    """Test successful AI callback that stores response in database"""
    payload = {
        "job_id": "job_456",
        "status": "completed",
        "output": {
            "answer": "Use 2-4 mg/L free chlorine for water treatment",
            "citations": [
                {
                    "document": "WHO Water Quality",
                    "chunk": "Free chlorine should be maintained at 2-4 mg/L",
                    "page": "5",
                }
            ],
        },
        "error": None,
        "callback_params": (
            f'{{"message_id": {test_message.id}, "message_type": 2, '
            f'"customer_id": {test_message.customer_id}}}'
        ),
        "trace_id": "trace_002",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

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
    client: TestClient, db_session: Session
):
    """Test AI callback with invalid message_id - should not store response"""
    payload = {
        "job_id": "job_invalid",
        "status": "completed",
        "output": {
            "answer": "Use 2-4 mg/L free chlorine for water treatment",
            "citations": [
                {
                    "document": "WHO Water Quality",
                    "chunk": (
                        "Free chlorine should be maintained at 2-4 mg/L"
                    ),
                    "page": "5",
                }
            ],
        },
        "error": None,
        "callback_params": (
            '{"message_id": 99999, "message_type": 1, "customer_id": 999}'
        ),
        "trace_id": "trace_invalid",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

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


def test_ai_callback_failed_job(client: TestClient, db_session: Session):
    """Test AI callback for failed job"""
    payload = {
        "job_id": "job_456",
        "status": "failed",
        "output": None,
        "error": "Prompt must accept context as an input variable",
        "callback_params": (
            '{"message_id": 456, "message_type": 1, "customer_id": 100}'
        ),
        "trace_id": "trace_002",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_456"}


def test_kb_callback_success(client: TestClient, db_session: Session):
    """Test successful KB callback"""
    payload = {
        "job_id": "kb_job_789",
        "status": "done",
        "callback_params": None,  # No KB params to avoid DB access
        "trace_id": "trace_003",
        "job": "upload",
    }

    response = client.post("/api/callback/kb", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "kb_job_789"}


def test_kb_callback_timeout(client: TestClient, db_session: Session):
    """Test KB callback for timeout"""
    payload = {
        "job_id": "kb_job_timeout",
        "status": "timeout",
        "callback_params": None,  # No KB params to avoid DB access
        "trace_id": "trace_004",
        "job": "upload",
    }

    response = client.post("/api/callback/kb", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "job_id": "kb_job_timeout",
    }


def test_callback_invalid_stage_enum(client: TestClient):
    """Test callback with invalid stage enum"""
    payload = {
        "job_id": "job_123",
        "status": "invalid_stage",  # Invalid enum value
        "output": None,
        "error": None,
        "callback_params": (
            '{"message_id": 123, "message_type": 1, "customer_id": 100}'
        ),
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 422  # Validation error


def test_callback_invalid_job_enum(client: TestClient):
    """Test callback with invalid job enum"""
    payload = {
        "job_id": "job_123",
        "status": "completed",
        "output": None,
        "error": None,
        "callback_params": (
            '{"message_id": 123, "message_type": 1, "customer_id": 100}'
        ),
        "job": "invalid_job",  # Invalid enum value
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 422  # Validation error


def test_callback_missing_required_fields(client: TestClient):
    """Test callback with missing required fields"""
    payload = {
        "job_id": "job_123",
        # Missing status and callback_params (both required)
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 422  # Validation error


def test_callback_with_all_optional_fields(client: TestClient):
    """Test callback with all optional fields included"""
    payload = {
        "job_id": "job_complete",
        "status": "completed",
        "output": {
            "answer": "Complete answer with citations",
            "citations": [
                {
                    "document": "Source 1",
                    "chunk": "Content from source 1",
                    "page": "10",
                },
                {
                    "document": "Source 2",
                    "chunk": "Content from source 2",
                    "page": "20",
                },
            ],
        },
        "error": None,
        "callback_params": (
            '{"message_id": 789, "message_type": 1, "customer_id": 100}'
        ),
        "trace_id": "trace_complete",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_complete"}


def test_callback_queued_stage(client: TestClient):
    """Test callback with queued stage"""
    payload = {
        "job_id": "job_queued",
        "status": "queued",
        "output": None,
        "error": None,
        "callback_params": (
            '{"message_id": 100, "message_type": 1, "customer_id": 100}'
        ),
        "job": "chat",
        "trace_id": "trace_queued",
    }

    response = client.post("/api/callback/ai", json=payload)

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
    test_customer_with_ticket,
    db_session: Session,
):
    """Test AI callback with WHISPER type and explicit ticket_id"""
    customer, ticket, message = test_customer_with_ticket

    payload = {
        "job_id": "whisper_job_001",
        "status": "completed",
        "output": {
            "answer": "Plant rice in well-drained soil with sunlight.",
            "citations": [
                {
                    "document": "Rice Growing Guide",
                    "chunk": "Rice requires well-drained soil",
                    "page": "12",
                }
            ],
        },
        "error": None,
        "callback_params": (
            f'{{"message_id": {message.id}, "message_type": 2, '
            f'"customer_id": {customer.id}, "ticket_id": {ticket.id}}}'
        ),
        "trace_id": "trace_whisper_001",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "job_id": "whisper_job_001",
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
    expected_body = "Plant rice in well-drained soil with sunlight."
    assert whisper_msg.body == expected_body
    assert whisper_msg.message_sid == "ai_whisper_job_001"
    assert whisper_msg.from_source == MessageFrom.LLM
    # Import MessageType to check the value
    from schemas.callback import MessageType

    assert whisper_msg.message_type == MessageType.WHISPER


def test_ai_callback_whisper_type_without_ticket_id(
    client: TestClient,
    test_customer_with_ticket,
    db_session: Session,
):
    """Test AI callback with WHISPER type, ticket_id found from customer"""
    customer, ticket, message = test_customer_with_ticket

    payload = {
        "job_id": "whisper_job_002",
        "status": "completed",
        "output": {
            "answer": "Use nitrogen-rich fertilizers for rice.",
            "citations": [
                {
                    "document": "Rice Fertilizer Guide",
                    "chunk": "Nitrogen-rich fertilizers improve rice yield",
                    "page": "8",
                }
            ],
        },
        "error": None,
        "callback_params": (
            f'{{"message_id": {message.id}, "message_type": 2, '
            f'"customer_id": {customer.id}}}'
        ),
        "trace_id": "trace_whisper_002",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

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
    test_customer_with_ticket,
    db_session: Session,
):
    """Test AI callback with WHISPER type when ticket is resolved"""
    from datetime import datetime, timezone

    customer, ticket, message = test_customer_with_ticket

    # Resolve the ticket
    ticket.resolved_at = datetime.now(timezone.utc)
    db_session.commit()

    payload = {
        "job_id": "whisper_job_003",
        "status": "completed",
        "output": {
            "answer": "This suggestion won't be sent anywhere.",
            "citations": [],
        },
        "error": None,
        "callback_params": (
            f'{{"message_id": {message.id}, "message_type": 2, '
            f'"customer_id": {customer.id}}}'
        ),
        "trace_id": "trace_whisper_003",
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

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
