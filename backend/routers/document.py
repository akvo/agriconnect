from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    DocumentListResponse,
    UploadDocumentResponse,
)
from services.external_ai_service import ExternalAIService
from services.knowledge_base_service import KnowledgeBaseService
from utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new Document",
    description="Upload a single file to be added to a Knowledge Base.",
)
async def create_document(
    file: UploadFile = File(..., description="Document file to upload"),
    kb_id: str = Form(
        ..., description="Knowledge Base ID this document belongs to"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload and register a document in a Knowledge Base."""
    allowed_types = [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # noqa
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file, only PDF, TXT, and DOCX are allowed.",
        )

    kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge Base not found.",
        )

    try:
        ai_service = ExternalAIService(db=db)
        if not ai_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No active AI service configured",
            )

        rag_doc_response = await ai_service.create_upload_job(
            upload_file=file,
            kb_id=kb.external_id,
            user_id=current_user.id,
        )

        if not rag_doc_response:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to upload document to external AI service.",
            )

        return UploadDocumentResponse(
            job_id=rag_doc_response.get("job_id"),
            status=rag_doc_response.get("status"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading document: {str(e)}",
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Documents",
    description="List all documents, or filtered by Knowledge Base ID.",
)
async def list_documents(
    kb_id: Optional[str] = Query(
        None, description="Filter by Knowledge Base ID"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all or filtered documents."""
    kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge Base not found.",
        )

    ai_service = ExternalAIService(db=db)
    if not ai_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active AI service configured",
        )

    rag_doc_response = await ai_service.manage_knowledge_base(
        operation="list_docs", kb_id=kb.external_id, is_doc=True
    )
    print(rag_doc_response, "xxxxx")
    # [
    #     {
    #         "id": 10,
    #         "file_name": "knowledge_base-agriculture_africa.docx",
    #         "status": "completed",
    #         "knowledge_base_id": 7,
    #         "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    #         "created_at": "2025-11-05T08:47:14.711127",
    #     },
    #     {
    #         "id": 9,
    #         "file_name": "websocket-issue-analysis.md",
    #         "status": "pending",
    #         "knowledge_base_id": 7,
    #         "content_type": "text/markdown",
    #         "created_at": "2025-11-05T08:46:52.909582",
    #     },
    # ]

    return DocumentListResponse(
        data=[],
        total=0,
        page=0,
        size=0,
    )
