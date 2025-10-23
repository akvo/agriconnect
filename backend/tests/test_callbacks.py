import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom


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
    client: TestClient, db_session: Session
):
    """Test successful AI callback"""
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


def test_ai_callback_failed_job(
    client: TestClient, db_session: Session
):
    """Test AI callback for failed job"""
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

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_456"}


def test_kb_callback_success(
    client: TestClient, db_session: Session
):
    """Test successful KB callback"""
    payload = {
        "job_id": "kb_job_789",
        "stage": "done",
        "callback_params": {"kb_id": 2, "user_id": 1},
        "trace_id": "trace_003",
        "job": "upload",
    }

    response = client.post("/api/callback/kb", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "kb_job_789"}


def test_kb_callback_timeout(
    client: TestClient, db_session: Session
):
    """Test KB callback for timeout"""
    payload = {
        "job_id": "kb_job_timeout",
        "stage": "timeout",
        "trace_id": "trace_004",
        "job": "upload",
    }

    response = client.post("/api/callback/kb", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "job_id": "kb_job_timeout",
    }


def test_callback_invalid_stage_enum(
    client: TestClient
):
    """Test callback with invalid stage enum"""
    payload = {
        "job_id": "job_123",
        "stage": "invalid_stage",  # Invalid enum value
        "job": "chat",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 422  # Validation error


def test_callback_invalid_job_enum(
    client: TestClient
):
    """Test callback with invalid job enum"""
    payload = {
        "job_id": "job_123",
        "stage": "done",
        "job": "invalid_job",  # Invalid enum value
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 422  # Validation error


def test_callback_missing_required_fields(
    client: TestClient
):
    """Test callback with missing required fields"""
    payload = {
        "job_id": "job_123",
        # Missing stage, job
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 422  # Validation error


def test_callback_with_all_optional_fields(
    client: TestClient
):
    """Test callback with all optional fields included"""
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

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_complete"}


def test_callback_queued_stage(client: TestClient):
    """Test callback with queued stage"""
    payload = {
        "job_id": "job_queued",
        "stage": "queued",
        "job": "chat",
        "trace_id": "trace_queued",
    }

    response = client.post("/api/callback/ai", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_queued"}
