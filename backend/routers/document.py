import os
import logging
import zipfile

from io import BytesIO
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
    DocumentResponse,
)
from services.external_ai_service import ExternalAIService
from services.knowledge_base_service import KnowledgeBaseService
from utils.auth_dependencies import get_current_user


logger = logging.getLogger(__name__)


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

    # ✅ Read file content ONCE and validate
    await file.seek(0)
    file_bytes = await file.read()
    file_size = len(file_bytes)

    logger.info("---- DEBUG: FILE RECEIVED ----")
    logger.info(f"filename: {file.filename}")
    logger.info(f"content_type: {file.content_type}")
    logger.info(f"file size: {file_size:,} bytes")
    logger.info(f"first 20 bytes (hex): {file_bytes[:20].hex()}")

    # Validate file type
    allowed_types = [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # noqa
    ]
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_ext = [".pdf", ".txt", ".docx"]

    if file.content_type not in allowed_types and ext not in allowed_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file, only PDF, TXT, and DOCX are allowed",
        )

    # ✅ Validate DOCX structure if applicable
    if ext == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
                logger.info(
                    f"✅ Valid DOCX structure ({len(zf.namelist())} entries)"
                )
        except zipfile.BadZipFile as e:
            logger.error(f"❌ Invalid DOCX from frontend: {e}")
            logger.error(f"First 50 bytes: {file_bytes[:50]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted DOCX file: {str(e)}",
            )

    # Validate KB exists
    kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge Base not found.",
        )

    # Check AI service
    ai_service = ExternalAIService(db=db)
    if not ai_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active AI service configured",
        )

    try:
        # ✅ Create a NEW UploadFile from the bytes we already read
        # Reset to a clean state with our validated bytes
        file_stream = BytesIO(file_bytes)
        clean_file = UploadFile(
            filename=file.filename,
            file=file_stream,
            # content_type=file.content_type,
        )

        logger.info(
            f"📤 Sending to RAG: {file.filename} ({file_size:,} bytes)"
        )

        rag_doc_response = await ai_service.create_upload_job(
            upload_file=clean_file,
            kb_id=kb.external_id,
            user_id=current_user.id,
        )

        if not rag_doc_response:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to upload document to external AI service.",
            )

        logger.info(
            f"✅ Upload successful: job_id={rag_doc_response.get('job_id')}"
        )

        return UploadDocumentResponse(
            job_id=rag_doc_response.get("job_id"),
            status=rag_doc_response.get("status"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ Error uploading document: {e}")
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
        operation="list_docs",
        kb_id=kb.external_id,
        is_doc=True,
        page=page,
        size=size,
        search=search,
    )

    # empty
    if not rag_doc_response.get("total"):
        return DocumentListResponse(
            data=[],
            total=0,
            page=0,
            size=0,
        )

    data = []
    for doc in rag_doc_response.get("data"):
        task = (
            doc.get("processing_tasks")[0]
            if doc.get("processing_tasks")
            else {}
        )
        data.append(
            DocumentResponse(
                id=doc.get("id"),
                filename=doc.get("file_name"),
                file_path=doc.get("file_path"),
                content_type=doc.get("content_type"),
                file_size=doc.get("file_size"),
                status=task.get("status"),
                created_at=task.get("created_at"),
                updated_at=task.get("updated_at"),
            )
        )

    return DocumentListResponse(
        data=data,
        total=rag_doc_response.get("total"),
        page=rag_doc_response.get("page"),
        size=rag_doc_response.get("size"),
    )
