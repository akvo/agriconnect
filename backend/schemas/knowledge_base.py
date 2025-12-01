from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    title: str = Field(..., description="Title for the knowledge base")
    description: Optional[str] = Field(
        None, description="Description of the KB"
    )
    is_active: bool = Field(False, description="Whether KB is active")


class KnowledgeBaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    title: str
    is_active: bool
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CreateKnowledgeBaseResponse(BaseModel):
    id: int
    user_id: int
    title: str
    is_active: bool
    description: Optional[str]

    class Config:
        from_attributes = True


class ToggleActiveKnowledgeBaseResponse(BaseModel):
    id: int
    user_id: int
    is_active: bool

    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    data: Optional[List[KnowledgeBaseResponse]] = []
    total: int
    page: int
    size: int
