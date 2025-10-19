import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class CustomerLanguage(enum.Enum):
    EN = "en"
    SW = "sw"


class CropType(enum.Enum):
    RICE = "rice"
    COFFEE = "coffee"
    CHILLI = "chilli"


class AgeGroup(enum.Enum):
    AGE_20_35 = "20-35"
    AGE_36_50 = "36-50"
    AGE_51_PLUS = "51+"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    language = Column(Enum(CustomerLanguage), default=CustomerLanguage.EN)
    crop_type = Column(Enum(CropType), nullable=True)
    age_group = Column(Enum(AgeGroup), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    messages = relationship(
        "Message", back_populates="customer", cascade="all, delete-orphan"
    )
    customer_administrative = relationship(
        "CustomerAdministrative", back_populates="customer"
    )
    tickets = relationship("Ticket", back_populates="customer")
