import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String, ForeignKey
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

    messages = relationship(
        "Message", back_populates="customer", cascade="all, delete-orphan"
    )
    customer_administrative = relationship(
        "CustomerAdministrative", back_populates="customer"
    )
    tickets = relationship("Ticket", back_populates="customer")
    crop_type = relationship(
        "CropType", back_populates="customers"
    )


class CropType(Base):
    __tablename__ = "crop_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customers = relationship(
        "Customer", back_populates="crop_type"
    )
