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


class UploadDocumentResponse(BaseModel):
    job_id: str
    status: str

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    data: List[DocumentResponse]
    total: int
    page: int
    size: int
