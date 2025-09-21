from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.callback import CallbackStage


class KnowledgeBaseCreate(BaseModel):
    """Schema for creating a knowledge base entry"""

    filename: str = Field(
        ..., description="Original filename of the uploaded file"
    )
    title: str = Field(..., description="Title for the knowledge base")
    description: Optional[str] = Field(
        None, description="Description of the knowledge base content"
    )
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata as JSON"
    )


class KnowledgeBaseUpdate(BaseModel):
    """Schema for updating a knowledge base entry"""

    title: Optional[str] = Field(None, description="Updated title")
    description: Optional[str] = Field(None, description="Updated description")
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Updated metadata"
    )


class KnowledgeBaseStatusUpdate(BaseModel):
    """Schema for updating KB status (used internally by callbacks)"""

    status: CallbackStage = Field(..., description="New status")


class KnowledgeBaseResponse(BaseModel):
    """Schema for knowledge base response"""

    id: int
    user_id: int
    filename: str
    title: str
    description: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    status: CallbackStage
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    """Schema for paginated knowledge base list"""

    knowledge_bases: List[KnowledgeBaseResponse]
    total: int
    skip: int
    limit: int
