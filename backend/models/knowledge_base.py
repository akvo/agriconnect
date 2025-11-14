from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    # Use String for external RAG compatibility (e.g. UUIDs)
    id = Column(String, primary_key=True, index=True)
    service_id = Column(
        Integer, ForeignKey("service_tokens.id"), nullable=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    extra_data = Column(JSONB, nullable=True)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="knowledge_bases")
    service = relationship("ServiceToken", back_populates="knowledge_bases")
    documents = relationship(
        "Document",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
