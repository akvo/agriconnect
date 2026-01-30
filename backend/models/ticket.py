import enum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class TicketTag(enum.IntEnum):
    """Tag categories for ticket classification"""
    FERTILIZER = 1
    PEST = 2
    PRE_PLANTING = 3
    HARVESTING = 4
    IRRIGATION = 5
    OTHER = 6


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), unique=True, nullable=False, index=True)
    administrative_id = Column(
        Integer,
        ForeignKey("administrative.id"),
        nullable=False
    )
    customer_id = Column(
        Integer, ForeignKey("customers.id"), nullable=False, index=True
    )
    message_id = Column(
        Integer, ForeignKey("messages.id"), nullable=False
    )
    context_message_id = Column(
        Integer, ForeignKey("messages.id"), nullable=True
    )
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    tag = Column(Integer, nullable=True)  # TicketTag enum value
    tag_confidence = Column(Float, nullable=True)  # AI confidence 0.0-1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer = relationship("Customer", back_populates="tickets")
    message = relationship("Message", foreign_keys=[message_id])
    context_message = relationship(
        "Message", foreign_keys=[context_message_id]
    )
    resolver = relationship("User")
    ticket_administrative = relationship(
        "Administrative", back_populates="tickets"
    )
