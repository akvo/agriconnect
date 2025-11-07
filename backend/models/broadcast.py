"""
Broadcast models for managing broadcast groups and messages.
"""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Enum
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from database import Base

# Import existing DeliveryStatus from message model
from models.message import DeliveryStatus


class BroadcastGroup(Base):
    """Broadcast Group with filter criteria for targeting broadcasts"""
    __tablename__ = "broadcast_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    crop_types = Column(JSON)  # Filter: crop_type IDs [1, 3, 5]
    age_groups = Column(JSON)  # Filter: age groups ["20-35", "36-50"]
    administrative_id = Column(
        Integer,
        ForeignKey("administrative.id"),
        nullable=True,
        index=True
    )
    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    administrative = relationship("Administrative", backref="broadcast_groups")
    creator = relationship("User", backref="broadcast_groups")
    group_contacts = relationship(
        "BroadcastGroupContact",
        back_populates="broadcast_group",
        cascade="all, delete-orphan"
    )
    broadcast_groups = relationship(
        "BroadcastMessageGroup",
        back_populates="broadcast_group"
    )


class BroadcastGroupContact(Base):
    """Junction table for group membership"""
    __tablename__ = "broadcast_group_contacts"

    id = Column(Integer, primary_key=True, index=True)
    broadcast_group_id = Column(
        Integer,
        ForeignKey("broadcast_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    broadcast_group = relationship(
        "BroadcastGroup", back_populates="group_contacts"
    )
    customer = relationship("Customer")

    # Constraint
    __table_args__ = (
        UniqueConstraint(
            'broadcast_group_id',
            'customer_id',
            name='unique_broadcast_group_contact'
        ),
    )


class BroadcastMessage(Base):
    """Broadcast Message - Campaign metadata"""
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    status = Column(String(50), default='pending')
    queued_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    creator = relationship("User", backref="broadcast_messages")
    broadcast_groups = relationship(
        "BroadcastMessageGroup",
        back_populates="broadcast_message",
        cascade="all, delete-orphan"
    )
    broadcast_recipients = relationship(
        "BroadcastRecipient",
        back_populates="broadcast_message",
        cascade="all, delete-orphan"
    )


class BroadcastMessageGroup(Base):
    """Junction table for broadcast → groups (many-to-many)"""
    __tablename__ = "broadcast_message_groups"

    id = Column(Integer, primary_key=True, index=True)
    broadcast_message_id = Column(
        Integer,
        ForeignKey("broadcast_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    broadcast_group_id = Column(
        Integer,
        ForeignKey("broadcast_groups.id"),
        nullable=False,
        index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    broadcast_message = relationship(
        "BroadcastMessage", back_populates="broadcast_groups"
    )
    broadcast_group = relationship(
        "BroadcastGroup", back_populates="broadcast_groups"
    )

    # Constraint
    __table_args__ = (
        UniqueConstraint(
            'broadcast_message_id',
            'broadcast_group_id',
            name='unique_broadcast_message_group'
        ),
    )


class BroadcastRecipient(Base):
    """Delivery tracking for individual recipients"""
    __tablename__ = "broadcast_recipients"

    id = Column(Integer, primary_key=True, index=True)
    broadcast_message_id = Column(
        Integer,
        ForeignKey("broadcast_messages.id", ondelete="CASCADE"),
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
    template_message_sid = Column(String(255))
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
    broadcast_message = relationship(
        "BroadcastMessage", back_populates="broadcast_recipients"
    )
    customer = relationship("Customer")
    message = relationship("Message")
