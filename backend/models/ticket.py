from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


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
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer = relationship("Customer", back_populates="tickets")
    message = relationship("Message")
    resolver = relationship("User")
    ticket_administrative = relationship(
        "Administrative", back_populates="tickets"
    )
