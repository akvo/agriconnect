import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class CustomerLanguage(enum.Enum):
    EN = "en"
    SW = "sw"


class AgeGroup(enum.Enum):
    AGE_20_35 = "20-35"
    AGE_36_50 = "36-50"
    AGE_51_PLUS = "51+"


class OnboardingStatus(enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    language = Column(Enum(CustomerLanguage), default=CustomerLanguage.EN)
    crop_type_id = Column(Integer, ForeignKey("crop_types.id"), nullable=True)
    age_group = Column(Enum(AgeGroup), nullable=True)
    age = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 24-hour reconnection tracking
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_message_from = Column(Integer, nullable=True)  # MessageFrom value

    # AI Onboarding tracking
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False,
    )
    onboarding_attempts = Column(Integer, default=0, nullable=False)
    onboarding_candidates = Column(
        Text, nullable=True
    )  # JSON array of ward IDs

    messages = relationship(
        "Message", back_populates="customer", cascade="all, delete-orphan"
    )
    customer_administrative = relationship(
        "CustomerAdministrative", back_populates="customer"
    )
    tickets = relationship("Ticket", back_populates="customer")
    crop_type = relationship("CropType", back_populates="customers")

    def needs_reconnection_template(self, threshold_hours: int = 24) -> bool:
        """
        Check if customer needs reconnection template.

        Returns True if:
        - Last message was from LLM/USER (outgoing from us)
        - More than threshold_hours have passed since last message

        Args:
            threshold_hours:
            Number of hours of inactivity before reconnection needed
        Returns:
            bool: True if reconnection template should be sent
        """
        if not self.last_message_at or not self.last_message_from:
            return False

        from datetime import datetime, timezone, timedelta
        from models.message import MessageFrom

        # Only need reconnection if last message was FROM us
        if self.last_message_from not in (MessageFrom.USER, MessageFrom.LLM):
            return False

        time_since_last = datetime.now(timezone.utc) - self.last_message_at
        return time_since_last > timedelta(hours=threshold_hours)


class CropType(Base):
    __tablename__ = "crop_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customers = relationship("Customer", back_populates="crop_type")
