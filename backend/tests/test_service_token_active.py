from sqlalchemy.orm import Session

from services.service_token_service import ServiceTokenService


def test_first_service_token_auto_activated(db_session: Session):
    """Test that the first service token is automatically activated"""
    # Create first service token
    service_token = ServiceTokenService.create_token(
        db_session, "first-service", "token1"
    )

    assert service_token.active == 1


def test_second_service_token_not_auto_activated(db_session: Session):
    """Test that subsequent service tokens are not automatically activated"""
    # Create first service token
    ServiceTokenService.create_token(
        db_session, "first-service", "token1"
    )

    # Create second service token
    service_token2 = ServiceTokenService.create_token(
        db_session, "second-service", "token2"
    )

    assert service_token2.active == 0


def test_explicitly_activate_service_token(db_session: Session):
    """Test explicitly activating a service token deactivates others"""
    # Create first service token (auto-activated)
    first_token = ServiceTokenService.create_token(
        db_session, "first-service", "token1"
    )
    assert first_token.active == 1

    # Create second service token with explicit activation
    second_token = ServiceTokenService.create_token(
        db_session, "second-service", "token2", active=1
    )

    # Refresh first token from database
    db_session.refresh(first_token)

    assert first_token.active == 0
    assert second_token.active == 1


def test_update_token_config_activation(db_session: Session):
    """Test that updating a token to active deactivates others"""
    # Create two service tokens
    first_token = ServiceTokenService.create_token(
        db_session, "first-service", "token1"
    )
    second_token = ServiceTokenService.create_token(
        db_session, "second-service", "token2"
    )

    assert first_token.active == 1  # First one auto-activated
    assert second_token.active == 0

    # Update second token to be active
    ServiceTokenService.update_token_config(
        db_session, second_token.id, active=1
    )

    # Refresh tokens from database
    db_session.refresh(first_token)
    db_session.refresh(second_token)

    assert first_token.active == 0
    assert second_token.active == 1


def test_get_active_token(db_session: Session):
    """Test getting the currently active service token"""
    # Initially no active tokens
    assert ServiceTokenService.get_active_token(db_session) is None

    # Create first service token (auto-activated)
    first_token = ServiceTokenService.create_token(
        db_session, "first-service", "token1"
    )

    active_token = ServiceTokenService.get_active_token(db_session)
    assert active_token is not None
    assert active_token.id == first_token.id
    assert active_token.service_name == "first-service"


def test_deactivate_token(db_session: Session):
    """Test deactivating a service token"""
    # Create service token (auto-activated)
    service_token = ServiceTokenService.create_token(
        db_session, "test-service", "token1"
    )
    assert service_token.active == 1

    # Deactivate it
    ServiceTokenService.update_token_config(
        db_session, service_token.id, active=0
    )

    # Refresh token from database
    db_session.refresh(service_token)
    assert service_token.active == 0

    # No active tokens
    assert ServiceTokenService.get_active_token(db_session) is None
