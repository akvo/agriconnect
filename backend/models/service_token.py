from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from database import Base


class ServiceToken(Base):
    __tablename__ = "service_tokens"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False, index=True, unique=True)
    # Fields for external service integration (outbound authentication)
    access_token = Column(
        String, nullable=True
    )  # Token to authenticate with external service
    chat_url = Column(String, nullable=True)  # URL for chat job requests
    upload_url = Column(
        String, nullable=True
    )  # URL for KB upload job requests
    active = Column(
        Integer, nullable=False, default=0, index=True
    )  # 0=inactive, 1=active, only one can be active

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
