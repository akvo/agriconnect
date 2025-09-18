import hashlib
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from models.service_token import ServiceToken


class ServiceTokenService:
    @staticmethod
    def create_token(
        db: Session,
        service_name: str,
        scopes: Optional[str] = None,
        access_token: Optional[str] = None,
        chat_url: Optional[str] = None,
        upload_url: Optional[str] = None,
    ) -> tuple[ServiceToken, str]:
        """Create a new service token and return the token and plain text."""
        # Generate a secure random token (256-bit)
        plain_token = secrets.token_urlsafe(32)

        # Hash the token for storage
        token_hash = hashlib.sha256(plain_token.encode()).hexdigest()

        service_token = ServiceToken(
            service_name=service_name,
            token_hash=token_hash,
            scopes=scopes,
            access_token=access_token,
            chat_url=chat_url,
            upload_url=upload_url,
        )

        db.add(service_token)
        db.commit()
        db.refresh(service_token)

        return service_token, plain_token

    @staticmethod
    def verify_token(db: Session, token: str) -> Optional[ServiceToken]:
        """Verify a service token and return the ServiceToken if valid."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        return (
            db.query(ServiceToken)
            .filter(ServiceToken.token_hash == token_hash)
            .first()
        )

    @staticmethod
    def get_token_by_service_name(
        db: Session, service_name: str
    ) -> Optional[ServiceToken]:
        """Get a service token by service name."""
        return (
            db.query(ServiceToken)
            .filter(ServiceToken.service_name == service_name)
            .first()
        )

    @staticmethod
    def update_token_config(
        db: Session,
        token_id: int,
        access_token: Optional[str] = None,
        chat_url: Optional[str] = None,
        upload_url: Optional[str] = None,
    ) -> Optional[ServiceToken]:
        """Update service token configuration with external service details."""
        token = (
            db.query(ServiceToken).filter(ServiceToken.id == token_id).first()
        )

        if not token:
            return None

        if access_token is not None:
            token.access_token = access_token
        if chat_url is not None:
            token.chat_url = chat_url
        if upload_url is not None:
            token.upload_url = upload_url

        db.commit()
        db.refresh(token)
        return token

    @staticmethod
    def delete_token(db: Session, token_id: int) -> bool:
        """Delete a service token by ID."""
        token = (
            db.query(ServiceToken).filter(ServiceToken.id == token_id).first()
        )

        if token:
            db.delete(token)
            db.commit()
            return True
        return False
