from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    title: str = Field(..., description="Title for the knowledge base")
    description: Optional[str] = Field(
        None, description="Description of the KB"
    )
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )


class KnowledgeBaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    user_id: int
    title: str
    description: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    data: List[KnowledgeBaseResponse]
    total: int
    page: int
    size: int
