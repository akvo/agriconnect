import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class PlaygroundMessageRole(enum.Enum):
    """Role of the message sender"""

    USER = "user"
    ASSISTANT = "assistant"


class PlaygroundMessageStatus(enum.Enum):
    """Status of assistant messages (NULL for user messages)"""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class PlaygroundMessage(Base):
    __tablename__ = "playground_messages"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(Enum(PlaygroundMessageRole), nullable=False)
    content = Column(Text, nullable=False)
    job_id = Column(String(100), nullable=True, index=True)
    status = Column(Enum(PlaygroundMessageStatus), nullable=True)
    custom_prompt = Column(Text, nullable=True)
    service_used = Column(String(100), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    admin_user = relationship("User")

    def __repr__(self):
        return (
            f"<PlaygroundMessage(id={self.id}, "
            f"role={self.role.value}, session_id={self.session_id})>"
        )
