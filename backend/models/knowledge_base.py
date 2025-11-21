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


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    # Primary key remains INTEGER
    id = Column(Integer, primary_key=True, index=True)

    # External ID returned by Akvo RAG (string, e.g. UUID)
    external_id = Column(String, nullable=True)

    # Who owns the knowledge base
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Which service token was used to create it (optional)
    service_id = Column(
        Integer,
        ForeignKey("service_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="knowledge_bases")
    service = relationship("ServiceToken", back_populates="knowledge_bases")
