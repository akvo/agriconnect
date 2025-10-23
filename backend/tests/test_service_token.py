import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from models.service_token import ServiceToken
from services.service_token_service import ServiceTokenService


def test_service_token_creation(db_session: Session):
    """Test creating a service token"""
    service_token = ServiceToken(
        service_name="test-service",
        access_token="akvo_token_123",
        chat_url="https://akvo-rag.example.com/chat",
        upload_url="https://akvo-rag.example.com/upload",
    )

    db_session.add(service_token)
    db_session.commit()
    db_session.refresh(service_token)

    assert service_token.id is not None
    assert service_token.service_name == "test-service"
    assert service_token.access_token == "akvo_token_123"
    assert service_token.chat_url == "https://akvo-rag.example.com/chat"
    assert service_token.upload_url == "https://akvo-rag.example.com/upload"
    assert service_token.created_at is not None
    assert service_token.updated_at is not None
    assert isinstance(service_token.created_at, datetime)
    assert isinstance(service_token.updated_at, datetime)


def test_service_token_repr(db_session: Session):
    """Test ServiceToken string representation"""
    service_token = ServiceToken(
        service_name="test-service",
        access_token="akvo_token_123"
    )

    db_session.add(service_token)
    db_session.commit()
    db_session.refresh(service_token)

    expected = (
        f"<ServiceToken(id={service_token.id}, service_name='test-service')>"
    )
    assert repr(service_token) == expected


def test_service_token_unique_service_name(db_session: Session):
    """Test that service_name must be unique"""
    # Create first token
    token1 = ServiceToken(service_name="duplicate-service", access_token="token1")
    db_session.add(token1)
    db_session.commit()

    # Try to create second token with same service_name
    token2 = ServiceToken(service_name="duplicate-service", access_token="token2")
    db_session.add(token2)

    with pytest.raises(Exception):  # Should raise integrity error
        db_session.commit()


def test_service_token_service_create_token(db_session: Session):
    """Test ServiceTokenService create_token method"""
    service_name = "akvo-rag"
    access_token = "akvo_access_token_123"
    chat_url = "https://akvo-rag.example.com/chat"
    upload_url = "https://akvo-rag.example.com/upload"

    service_token = ServiceTokenService.create_token(
        db_session, service_name, access_token, chat_url, upload_url
    )

    # Check that service token was created
    assert service_token.id is not None
    assert service_token.service_name == service_name
    assert service_token.access_token == access_token
    assert service_token.chat_url == chat_url
    assert service_token.upload_url == upload_url

    # Verify token can be found by service name
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert found_token is not None
    assert found_token.id == service_token.id


def test_service_token_service_delete_token(db_session: Session):
    """Test ServiceTokenService delete_token method"""
    service_name = "test-service"

    # Create a token
    service_token = ServiceTokenService.create_token(
        db_session, service_name
    )
    token_id = service_token.id

    # Verify token exists
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert found_token is not None

    # Delete the token
    success = ServiceTokenService.delete_token(db_session, token_id)
    assert success is True

    # Verify token no longer exists
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert found_token is None

    # Try to delete non-existent token
    success = ServiceTokenService.delete_token(db_session, 99999)
    assert success is False


def test_service_token_service_get_token_by_service_name(db_session: Session):
    """Test ServiceTokenService get_token_by_service_name method"""
    service_name = "test-service"

    # Token doesn't exist yet
    token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert token is None

    # Create a token
    service_token = ServiceTokenService.create_token(
        db_session, service_name
    )

    # Now it should be found
    token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert token is not None
    assert token.id == service_token.id
    assert token.service_name == service_name


def test_service_token_minimal_fields(db_session: Session):
    """Test creating service token with only service_name"""
    service_name = "simple-service"

    service_token = ServiceTokenService.create_token(
        db_session, service_name
    )

    assert service_token.access_token is None
    assert service_token.chat_url is None
    assert service_token.upload_url is None
    assert service_token.service_name == service_name
