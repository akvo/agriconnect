from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Device(Base):
    """
    Device model for storing push notification tokens.

    Tracks mobile devices registered for push notifications.
    Devices are associated with administrative areas (wards) rather than
    individual users, since the same device might be used by different users.
    """

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    administrative_id = Column(
        Integer, ForeignKey("administrative.id"), nullable=False, index=True
    )
    push_token = Column(String, unique=True, nullable=False, index=True)
    app_version = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    administrative = relationship("Administrative", back_populates="devices")
