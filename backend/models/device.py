import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class DevicePlatform(enum.Enum):
    IOS = "ios"
    ANDROID = "android"


class Device(Base):
    """
    Device model for storing push notification tokens.

    Tracks mobile devices registered for push notifications.
    Each user can have multiple devices (phone, tablet, etc.).
    """

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    push_token = Column(String, unique=True, nullable=False, index=True)
    platform = Column(Enum(DevicePlatform), nullable=False)
    app_version = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="devices")
