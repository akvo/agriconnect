import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.service_token_service import ServiceTokenService


@pytest.fixture
def service_token_and_plain(db_session: Session):
    """Create a service token for testing"""
    service_token, plain_token = ServiceTokenService.create_token(
        db_session, "akvo-rag", "callback:write"
    )
    return service_token, plain_token


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
            "reply_to": "wa:+679123456",
            "conversation_id": "conv_123",
            "kb_id": 1,
        },
        "trace_id": "trace_001",
        "event_type": "result",
        "job": "chat",
        "tenant_id": "tenant-x",
        "app_id": "app_123",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_123"}


def test_ai_callback_failed_job(
    client: TestClient, service_token_and_plain, db_session: Session
):
    """Test AI callback for failed job"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_456",
        "stage": "failed",
        "callback_params": {
            "reply_to": "wa:+679123456",
            "conversation_id": "conv_123",
        },
        "trace_id": "trace_002",
        "event_type": "error",
        "job": "chat",
        "tenant_id": "tenant-x",
        "app_id": "app_123",
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
        "callback_params": {"kb_id": 2},
        "trace_id": "trace_003",
        "event_type": "result",
        "job": "upload",
        "tenant_id": "tenant-y",
        "app_id": "app_456",
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
        "event_type": "error",
        "job": "upload",
        "tenant_id": "tenant-z",
        "app_id": "app_789",
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
        "event_type": "result",
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
        "event_type": "result",
        "job": "chat",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 422  # Validation error


def test_callback_invalid_event_type_enum(
    client: TestClient, service_token_and_plain
):
    """Test callback with invalid event_type enum"""
    _, plain_token = service_token_and_plain

    payload = {
        "job_id": "job_123",
        "stage": "done",
        "event_type": "invalid_event",  # Invalid enum value
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
        "event_type": "result",
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
        # Missing stage, event_type, job
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
            "reply_to": "wa:+1234567890",
            "conversation_id": "conv_full",
            "kb_id": 5,
        },
        "trace_id": "trace_complete",
        "event_type": "result",
        "job": "chat",
        "tenant_id": "tenant-complete",
        "app_id": "app_complete",
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
        "event_type": "result",
        "job": "chat",
        "trace_id": "trace_queued",
    }

    headers = {"Authorization": f"Bearer {plain_token}"}

    response = client.post("/api/callback/ai", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "job_id": "job_queued"}
