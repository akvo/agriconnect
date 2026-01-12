"""
Weather broadcast models for daily weather messaging.
"""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Enum
)
from sqlalchemy.orm import relationship
from database import Base
from models.message import DeliveryStatus


class WeatherBroadcast(Base):
    """Weather Broadcast - Daily weather message per administrative area"""
    __tablename__ = "weather_broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    administrative_id = Column(
        Integer,
        ForeignKey("administrative.id"),
        nullable=False,
        index=True
    )
    location_name = Column(String(255), nullable=False)
    weather_data = Column(JSON, nullable=True)  # Raw API response
    generated_message_en = Column(Text, nullable=True)
    generated_message_sw = Column(Text, nullable=True)
    status = Column(String(50), default='pending')
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    administrative = relationship("Administrative")
    recipients = relationship(
        "WeatherBroadcastRecipient",
        back_populates="weather_broadcast",
        cascade="all, delete-orphan"
    )


class WeatherBroadcastRecipient(Base):
    """Delivery tracking for weather broadcast recipients"""
    __tablename__ = "weather_broadcast_recipients"

    id = Column(Integer, primary_key=True, index=True)
    weather_broadcast_id = Column(
        Integer,
        ForeignKey("weather_broadcasts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )
    status = Column(
        Enum(DeliveryStatus),
        nullable=False,
        server_default=DeliveryStatus.PENDING.value,
        index=True
    )
    confirm_message_sid = Column(String(255), index=True)  # For webhook lookup
    actual_message_sid = Column(String(255))
    message_id = Column(Integer, ForeignKey("messages.id"))
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    sent_at = Column(DateTime)
    confirmed_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    weather_broadcast = relationship(
        "WeatherBroadcast", back_populates="recipients"
    )
    customer = relationship("Customer")
    message = relationship("Message")
