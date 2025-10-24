import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.user import User, UserType
from services.service_token_service import ServiceTokenService


@pytest.fixture
def admin_user(db_session: Session):
    """Create an admin user for testing"""
    user_data = {
        "email": "admin@test.com",
        "phone_number": "+1234567890",
        "full_name": "Test Admin",
        "user_type": UserType.ADMIN,
        "hashed_password": "hashed_password",
        "is_active": True,
    }
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session: Session):
    """Create a regular user for testing"""
    user_data = {
        "email": "user@test.com",
        "phone_number": "+0987654321",
        "full_name": "Test User",
        "user_type": UserType.EXTENSION_OFFICER,
        "hashed_password": "hashed_password",
        "is_active": True,
    }
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_auth_headers(admin_user):
    """Create auth headers for admin user"""
    from utils.auth import create_access_token

    token = create_access_token({"sub": admin_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_auth_headers(regular_user):
    """Create auth headers for regular user"""
    from utils.auth import create_access_token

    token = create_access_token({"sub": regular_user.email})
    return {"Authorization": f"Bearer {token}"}


def test_create_service_token_success(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test creating service token as admin"""
    payload = {
        "service_name": "akvo-rag",
        "access_token": "akvo_token_123",
        "chat_url": "https://akvo-rag.example.com/chat",
        "upload_url": "https://akvo-rag.example.com/upload",
    }

    response = client.post(
        "/api/admin/service-tokens/", json=payload, headers=admin_auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert data["service_name"] == "akvo-rag"
    assert data["access_token"] == "akvo_token_123"
    assert data["chat_url"] == "https://akvo-rag.example.com/chat"
    assert data["upload_url"] == "https://akvo-rag.example.com/upload"
    assert "created_at" in data
    assert "updated_at" in data


def test_create_service_token_duplicate_service_name(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test creating service token with duplicate service name"""
    # Create first token
    ServiceTokenService.create_token(db_session, "duplicate-service")

    payload = {"service_name": "duplicate-service"}

    response = client.post(
        "/api/admin/service-tokens/", json=payload, headers=admin_auth_headers
    )

    assert response.status_code == 400
    assert (
        "Service token already exists for 'duplicate-service'"
        in response.json()["detail"]
    )


def test_create_service_token_minimal_fields(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test creating service token with only service_name"""
    payload = {"service_name": "minimal-service"}

    response = client.post(
        "/api/admin/service-tokens/", json=payload, headers=admin_auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["service_name"] == "minimal-service"
    assert data["access_token"] is None
    assert data["chat_url"] is None
    assert data["upload_url"] is None


def test_create_service_token_non_admin(
    client: TestClient, user_auth_headers, db_session: Session
):
    """Test creating service token as non-admin user"""
    payload = {"service_name": "test-service"}

    response = client.post(
        "/api/admin/service-tokens/", json=payload, headers=user_auth_headers
    )

    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


def test_create_service_token_unauthenticated(
    client: TestClient, db_session: Session
):
    """Test creating service token without authentication"""
    payload = {"service_name": "test-service"}

    response = client.post("/api/admin/service-tokens/", json=payload)

    assert response.status_code == 403


def test_list_service_tokens_success(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test listing service tokens as admin"""
    # Create some test tokens
    ServiceTokenService.create_token(db_session, "service1", "token1")
    ServiceTokenService.create_token(db_session, "service2", "token2")
    ServiceTokenService.create_token(db_session, "service3", None)

    response = client.get(
        "/api/admin/service-tokens/", headers=admin_auth_headers
    )

    assert response.status_code == 200
    tokens = response.json()

    assert isinstance(tokens, list)
    assert len(tokens) == 3

    # Check first token
    token1 = tokens[0]
    assert "id" in token1
    assert "service_name" in token1
    assert "access_token" in token1
    assert "chat_url" in token1
    assert "upload_url" in token1
    assert "created_at" in token1
    assert "updated_at" in token1

    # Verify service names
    service_names = [token["service_name"] for token in tokens]
    assert "service1" in service_names
    assert "service2" in service_names
    assert "service3" in service_names


def test_list_service_tokens_empty(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test listing service tokens when none exist"""
    response = client.get(
        "/api/admin/service-tokens/", headers=admin_auth_headers
    )

    assert response.status_code == 200
    tokens = response.json()

    assert isinstance(tokens, list)
    assert len(tokens) == 0


def test_list_service_tokens_non_admin(
    client: TestClient, user_auth_headers, db_session: Session
):
    """Test listing service tokens as non-admin user"""
    response = client.get(
        "/api/admin/service-tokens/", headers=user_auth_headers
    )

    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


def test_delete_service_token_success(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test deleting service token as admin"""
    # Create a test token
    service_token = ServiceTokenService.create_token(
        db_session, "delete-me"
    )
    token_id = service_token.id

    # Verify token exists
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, "delete-me"
    )
    assert found_token is not None

    # Delete the token
    response = client.delete(
        f"/api/admin/service-tokens/{token_id}", headers=admin_auth_headers
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Service token deleted successfully"}

    # Verify token no longer exists
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, "delete-me"
    )
    assert found_token is None


def test_delete_service_token_not_found(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test deleting non-existent service token"""
    response = client.delete(
        "/api/admin/service-tokens/99999", headers=admin_auth_headers
    )

    assert response.status_code == 404
    assert "Service token not found" in response.json()["detail"]


def test_delete_service_token_non_admin(
    client: TestClient, user_auth_headers, db_session: Session
):
    """Test deleting service token as non-admin user"""
    # Create a test token
    service_token = ServiceTokenService.create_token(
        db_session, "test-service"
    )
    token_id = service_token.id

    response = client.delete(
        f"/api/admin/service-tokens/{token_id}", headers=user_auth_headers
    )

    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


def test_delete_service_token_unauthenticated(
    client: TestClient, db_session: Session
):
    """Test deleting service token without authentication"""
    response = client.delete("/api/admin/service-tokens/1")

    assert response.status_code == 403


def test_create_service_token_invalid_payload(
    client: TestClient, admin_auth_headers
):
    """Test creating service token with invalid payload"""
    payload = {
        # Missing service_name
        "access_token": "test_token"
    }

    response = client.post(
        "/api/admin/service-tokens/", json=payload, headers=admin_auth_headers
    )

    assert response.status_code == 422  # Validation error

def test_service_token_workflow_integration(
    client: TestClient, admin_auth_headers, db_session: Session
):
    """Test full workflow: create, list, delete"""
    # 1. Create a service token
    create_payload = {
        "service_name": "integration-test",
        "access_token": "integration_token_123",
        "chat_url": "https://example.com/chat",
        "upload_url": "https://example.com/upload",
    }

    create_response = client.post(
        "/api/admin/service-tokens/",
        json=create_payload,
        headers=admin_auth_headers,
    )

    assert create_response.status_code == 200
    create_data = create_response.json()
    token_id = create_data["id"]

    # 2. Verify token appears in list
    list_response = client.get(
        "/api/admin/service-tokens/", headers=admin_auth_headers
    )
    assert list_response.status_code == 200
    tokens = list_response.json()

    token_found = False
    for token in tokens:
        if token["id"] == token_id:
            assert token["service_name"] == "integration-test"
            assert token["access_token"] == "integration_token_123"
            assert token["chat_url"] == "https://example.com/chat"
            assert token["upload_url"] == "https://example.com/upload"
            token_found = True
            break

    assert token_found, "Created token not found in list"

    # 3. Delete the token
    delete_response = client.delete(
        f"/api/admin/service-tokens/{token_id}", headers=admin_auth_headers
    )

    assert delete_response.status_code == 200

    # Verify token is deleted from database
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, "integration-test"
    )
    assert found_token is None
