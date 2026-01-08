import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    JSON,
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


class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    language = Column(Enum(CustomerLanguage), default=None, nullable=True)
    # JSON object with profile fields
    profile_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 24-hour reconnection tracking
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_message_from = Column(Integer, nullable=True)  # MessageFrom value

    # Generic Onboarding tracking
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False,
    )
    current_onboarding_field = Column(
        String, nullable=True
    )  # Current field being collected
    onboarding_attempts = Column(
        JSON, nullable=True
    )  # JSON object: {"field_name": attempt_count}
    onboarding_candidates = Column(
        JSON, nullable=True
    )  # JSON object: {"field_name": [candidate_values]}

    messages = relationship(
        "Message", back_populates="customer", cascade="all, delete-orphan"
    )
    customer_administrative = relationship(
        "CustomerAdministrative", back_populates="customer"
    )
    tickets = relationship("Ticket", back_populates="customer")

    # Profile data property accessors
    @property
    def birth_year(self) -> int | None:
        """Get birth_year from profile_data"""
        if not self.profile_data:
            return None
        return self.profile_data.get("birth_year")

    @property
    def crop_type(self) -> str | None:
        """Get crop_type from profile_data"""
        if not self.profile_data:
            return None
        return self.profile_data.get("crop_type")

    @property
    def gender(self) -> str | None:
        """Get gender from profile_data"""
        if not self.profile_data:
            return None
        return self.profile_data.get("gender")

    @property
    def age(self) -> int | None:
        """Calculate current age from birth_year"""
        if not self.birth_year:
            return None
        from datetime import datetime

        current_year = datetime.now().year
        return current_year - self.birth_year

    @property
    def age_group(self) -> str | None:
        """Calculate age group from birth_year"""
        age = self.age
        if age is None:
            return None
        if 20 <= age <= 35:
            return "20-35"
        elif 36 <= age <= 50:
            return "36-50"
        else:
            return "51+"

    # Weather subscription properties
    @property
    def weather_subscription_asked(self) -> bool:
        """Check if weather subscription question was asked."""
        return self.get_profile_field("weather_subscription_asked", False)

    @weather_subscription_asked.setter
    def weather_subscription_asked(self, value: bool):
        self.set_profile_field("weather_subscription_asked", value)

    @property
    def weather_subscribed(self) -> bool | None:
        """Weather subscription status:
        True=subscribed, False=declined, None=not asked.
        """
        return self.get_profile_field("weather_subscribed", None)

    @weather_subscribed.setter
    def weather_subscribed(self, value: bool | None):
        self.set_profile_field("weather_subscribed", value)

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

    # Profile data helper methods
    def get_profile_field(self, field_name: str, default=None):
        """Get a field from profile_data"""
        if not self.profile_data:
            return default
        return self.profile_data.get(field_name, default)

    def set_profile_field(self, field_name: str, value):
        """Set a field in profile_data (triggers SQLAlchemy update)"""
        if not self.profile_data:
            self.profile_data = {}
        profile_dict = self.profile_data.copy()
        profile_dict[field_name] = value
        self.profile_data = profile_dict

    def update_profile_data(self, updates: dict):
        """Update multiple fields in profile_data at once"""
        if not self.profile_data:
            self.profile_data = {}
        profile_dict = self.profile_data.copy()
        profile_dict.update(updates)
        self.profile_data = profile_dict


class CropType(Base):
    __tablename__ = "crop_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
