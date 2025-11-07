from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    kb_id: str
    user_id: int
    filename: str
    file_path: Optional[str]
    content_type: Optional[str]
    file_size: Optional[int]
    status: str
    extra_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    """Used to update document metadata (title/description in extra_data)."""

    title: Optional[str] = None
    description: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    data: List[DocumentResponse]
    total: int
    page: int
    size: int
