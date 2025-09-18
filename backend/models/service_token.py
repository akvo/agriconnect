from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from database import Base


class ServiceToken(Base):
    __tablename__ = "service_tokens"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    scopes = Column(String, nullable=True)  # JSON string for scopes
    # Fields for external service integration
    access_token = Column(
        String, nullable=True
    )  # Token provided by external service
    chat_url = Column(String, nullable=True)  # URL for chat job requests
    upload_url = Column(
        String, nullable=True
    )  # URL for KB upload job requests

    created_at = Column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return (
            f"<ServiceToken(id={self.id}, "
            f"service_name='{self.service_name}')>"
        )
