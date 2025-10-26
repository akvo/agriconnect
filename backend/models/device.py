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
    Devices are associated with both:
    - administrative areas (wards) for ward-based notification filtering
    - users (current logged-in user) for user-based notification filtering

    This hybrid approach allows:
    - Efficient ward-based queries
    - Excluding specific users (e.g., message sender)
    - Proper session tracking (who is logged in on which device)
    """

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
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
    user = relationship("User", back_populates="devices")
    administrative = relationship("Administrative", back_populates="devices")
