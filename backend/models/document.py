from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Enum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from schemas.callback import CallbackStage

from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(
        String,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    status = Column(
        Enum(CallbackStage), default=CallbackStage.QUEUED, nullable=False
    )
    extra_data = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    user = relationship("User")
