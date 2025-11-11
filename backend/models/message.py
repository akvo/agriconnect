import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base
from schemas.callback import MessageType


class MessageFrom:
    CUSTOMER = 1
    USER = 2
    LLM = 3


class MessageStatus:
    """Business logic status (kept for backward compatibility)"""
    PENDING = 1
    REPLIED = 2
    RESOLVED = 3
    ESCALATED = 4  # Farmer requested human help after AI response


class DeliveryStatus(enum.Enum):
    """Twilio delivery status tracking"""
    PENDING = "PENDING"          # Initial state, not sent yet
    QUEUED = "QUEUED"            # Twilio accepted, queuing
    SENDING = "SENDING"          # Twilio sending to WhatsApp
    SENT = "SENT"                # Sent to WhatsApp servers
    DELIVERED = "DELIVERED"      # Delivered to device
    READ = "READ"                # Customer read (if callbacks enabled)
    FAILED = "FAILED"            # Permanent failure
    UNDELIVERED = "UNDELIVERED"  # Temporary failure/expired


class MediaType(enum.Enum):
    """Type of media in message"""
    TEXT = "TEXT"              # Regular text message (default)
    VOICE = "VOICE"            # Voice/audio message
    IMAGE = "IMAGE"            # Image (future)
    VIDEO = "VIDEO"            # Video (future)
    DOCUMENT = "DOCUMENT"      # PDF/document (future)
    LOCATION = "LOCATION"      # Geolocation (future)
    OTHER = "OTHER"            # Unknown media type


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_sid = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    from_source = Column(Integer, nullable=False)
    message_type = Column(Enum(MessageType), nullable=True)

    # Business logic status (kept for backward compatibility)
    status = Column(
        Integer,
        nullable=False,
        server_default=str(MessageStatus.PENDING),
        index=True,
    )

    # Delivery tracking fields
    delivery_status = Column(
        Enum(DeliveryStatus),
        nullable=False,
        server_default=DeliveryStatus.PENDING.value,
        index=True,
    )
    twilio_error_code = Column(String(10), nullable=True)
    twilio_error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default="0")
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Media tracking (for voice, images, etc.)
    media_url = Column(String, nullable=True)
    media_type = Column(
        Enum(MediaType),
        nullable=False,
        server_default=MediaType.TEXT.value,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="messages")
    user = relationship("User")

    def is_delivery_failed(self) -> bool:
        """Check if message delivery permanently failed"""
        return self.delivery_status in (
            DeliveryStatus.FAILED, DeliveryStatus.UNDELIVERED
        )

    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if message can be retried"""
        return (
            self.delivery_status in (
                DeliveryStatus.PENDING, DeliveryStatus.FAILED
            )
            and self.retry_count < max_retries
        )
