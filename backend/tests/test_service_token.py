import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from models.service_token import ServiceToken
from services.service_token_service import ServiceTokenService


def test_service_token_creation(db_session: Session):
    """Test creating a service token"""
    service_token = ServiceToken(
        service_name="test-service",
        token_hash="test_hash_123",
        scopes="callback:write",
    )

    db_session.add(service_token)
    db_session.commit()
    db_session.refresh(service_token)

    assert service_token.id is not None
    assert service_token.service_name == "test-service"
    assert service_token.token_hash == "test_hash_123"
    assert service_token.scopes == "callback:write"
    assert service_token.created_at is not None
    assert service_token.updated_at is not None
    assert isinstance(service_token.created_at, datetime)
    assert isinstance(service_token.updated_at, datetime)


def test_service_token_repr(db_session: Session):
    """Test ServiceToken string representation"""
    service_token = ServiceToken(
        service_name="test-service", token_hash="test_hash_123"
    )

    db_session.add(service_token)
    db_session.commit()
    db_session.refresh(service_token)

    expected = (
        f"<ServiceToken(id={service_token.id}, service_name='test-service')>"
    )
    assert repr(service_token) == expected


def test_service_token_unique_token_hash(db_session: Session):
    """Test that token_hash must be unique"""
    # Create first token
    token1 = ServiceToken(service_name="service1", token_hash="duplicate_hash")
    db_session.add(token1)
    db_session.commit()

    # Try to create second token with same hash
    token2 = ServiceToken(service_name="service2", token_hash="duplicate_hash")
    db_session.add(token2)

    with pytest.raises(Exception):  # Should raise integrity error
        db_session.commit()


def test_service_token_service_create_token(db_session: Session):
    """Test ServiceTokenService create_token method"""
    service_name = "akvo-rag"
    scopes = "callback:write,kb:read"

    service_token, plain_token = ServiceTokenService.create_token(
        db_session, service_name, scopes
    )

    # Check that service token was created
    assert service_token.id is not None
    assert service_token.service_name == service_name
    assert service_token.scopes == scopes
    assert service_token.token_hash is not None

    # Check that plain token is different from hash
    assert plain_token != service_token.token_hash
    assert len(plain_token) > 0

    # Verify token can be found by service name
    found_token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert found_token is not None
    assert found_token.id == service_token.id


def test_service_token_service_verify_token(db_session: Session):
    """Test ServiceTokenService verify_token method"""
    service_name = "test-service"

    # Create a token
    service_token, plain_token = ServiceTokenService.create_token(
        db_session, service_name
    )

    # Verify with correct token
    verified_token = ServiceTokenService.verify_token(db_session, plain_token)
    assert verified_token is not None
    assert verified_token.id == service_token.id
    assert verified_token.service_name == service_name

    # Verify with incorrect token
    invalid_token = ServiceTokenService.verify_token(
        db_session, "invalid_token"
    )
    assert invalid_token is None


def test_service_token_service_delete_token(db_session: Session):
    """Test ServiceTokenService delete_token method"""
    service_name = "test-service"

    # Create a token
    service_token, _ = ServiceTokenService.create_token(
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
    service_token, _ = ServiceTokenService.create_token(
        db_session, service_name
    )

    # Now it should be found
    token = ServiceTokenService.get_token_by_service_name(
        db_session, service_name
    )
    assert token is not None
    assert token.id == service_token.id
    assert token.service_name == service_name


def test_service_token_without_scopes(db_session: Session):
    """Test creating service token without scopes"""
    service_name = "simple-service"

    service_token, plain_token = ServiceTokenService.create_token(
        db_session, service_name
    )

    assert service_token.scopes is None
    assert plain_token is not None

    # Verify token works
    verified_token = ServiceTokenService.verify_token(db_session, plain_token)
    assert verified_token is not None
    assert verified_token.service_name == service_name
