import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class UserType(enum.Enum):
    ADMIN = "admin"
    EXTENSION_OFFICER = "eo"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    user_type = Column(Enum(UserType), nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    invitation_token = Column(String, unique=True, nullable=True)
    invitation_sent_at = Column(DateTime(timezone=True), nullable=True)
    invitation_expires_at = Column(DateTime(timezone=True), nullable=True)
    password_set_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user_administrative = relationship(
        "UserAdministrative", back_populates="user"
    )
    devices = relationship(
        "Device", back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_bases = relationship(
        "KnowledgeBase", back_populates="user", cascade="all, delete-orphan"
    )
