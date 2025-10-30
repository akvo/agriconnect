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
from models.knowledge_base import KnowledgeBase
from models.user import User
from schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseStatusUpdate,
    KnowledgeBaseUpdate,
)
from services.knowledge_base_service import KnowledgeBaseService
from utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/kb", tags=["knowledge_base"])


@router.post(
    "/",
    response_model=KnowledgeBaseResponse,
    summary="Upload Knowledge Base File",
    # flake8: noqa: E501
    description="Upload a file and create a knowledge base entry. The file will be processed by the configured external AI service.",
)
@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    summary="Upload Knowledge Base File (without trailing slash)",
    # flake8: noqa: E501
    description="Upload a file and create a knowledge base entry. The file will be processed by the configured external AI service.",
)
async def create_knowledge_base(
    file: UploadFile = File(..., description="File to upload"),
    title: str = Form(..., description="Title for the knowledge base"),
    description: str = Form(None, description="Description of the content"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new knowledge base entry with file upload"""
    try:
        # TODO: Implement file upload to storage (S3, local, etc.)
        # For now, we just store the filename

        # Validate file type (optional)
        if file.content_type not in [
            "application/pdf",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Only PDF, TXT, and DOCX files are allowed.",
            )

        # Create extra data from file info
        extra_data = {
            "original_filename": file.filename,
            "content_type": file.content_type,
            "size": file.size if hasattr(file, "size") else None,
        }

        kb_service = KnowledgeBaseService(db)
        kb = kb_service.create_knowledge_base(
            user_id=current_user.id,
            filename=file.filename,
            title=title,
            description=description,
            extra_data=extra_data,
        )

        # Send file to external AI service for processing
        from services.external_ai_service import ExternalAIService
        ai_service = ExternalAIService(db)
        if ai_service.is_configured() and ai_service.token.upload_url:
            # TODO: Implement file upload when ready
            # job_response = await ai_service.create_upload_job(
            #     file_path=...,
            #     kb_id=kb.id,
            #     metadata=extra_data
            # )
            pass

        return kb

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating knowledge base: {str(e)}",
        )


@router.get(
    "/",
    response_model=KnowledgeBaseListResponse,
    summary="List Knowledge Bases",
    # flake8: noqa: E501
    description="Get paginated list of knowledge bases. Admin users see all, regular users see only their own.",
)
@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    summary="List Knowledge Bases (without trailing slash)",
    # flake8: noqa: E501
    description="Get paginated list of knowledge bases. Admin users see all, regular users see only their own.",
)
async def list_knowledge_bases(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Number of records per page"),
    search: Optional[str] = Query(None, description="Search term"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated list of knowledge bases with optional search"""
    kb_service = KnowledgeBaseService(db)

    # If user is admin, show all knowledge bases
    # Otherwise, show only user's own knowledge bases
    if current_user.user_type.value == "admin":
        knowledge_bases, total = kb_service.get_all_knowledge_bases(
            page=page, size=size, search=search
        )
    else:
        knowledge_bases, total = kb_service.get_user_knowledge_bases(
            current_user.id, page=page, size=size, search=search
        )

    return KnowledgeBaseListResponse(
        knowledge_bases=knowledge_bases,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    summary="Get Knowledge Base",
    # flake8: noqa: E501
    description="Get a specific knowledge base by ID. Users can only access their own KBs unless they are admin.",
)
async def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get knowledge base by ID"""
    kb_service = KnowledgeBaseService(db)
    kb = kb_service.get_knowledge_base_by_id(kb_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    # Check permissions: users can only access their own KBs unless admin
    if current_user.user_type.value != "admin" and kb.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this knowledge base",
        )

    return kb


@router.put(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    summary="Update Knowledge Base",
    description="Update knowledge base metadata. Users can only update their own KBs unless they are admin.",
)
async def update_knowledge_base(
    kb_id: int,
    kb_update: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update knowledge base"""
    kb_service = KnowledgeBaseService(db)
    kb = kb_service.get_knowledge_base_by_id(kb_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    # Check permissions
    if current_user.user_type.value != "admin" and kb.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this knowledge base",
        )

    updated_kb = kb_service.update_knowledge_base(
        kb_id=kb_id,
        title=kb_update.title,
        description=kb_update.description,
        extra_data=kb_update.extra_data,
    )

    return updated_kb


@router.delete(
    "/{kb_id}",
    summary="Delete Knowledge Base",
    description="Delete a knowledge base. Users can only delete their own KBs unless they are admin.",
)
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete knowledge base"""
    kb_service = KnowledgeBaseService(db)
    kb = kb_service.get_knowledge_base_by_id(kb_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    # Check permissions
    if current_user.user_type.value != "admin" and kb.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this knowledge base",
        )

    success = kb_service.delete_knowledge_base(kb_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge base",
        )

    return {"message": "Knowledge base deleted successfully"}


@router.patch(
    "/{kb_id}/status",
    response_model=KnowledgeBaseResponse,
    summary="Update Knowledge Base Status",
    description="Update the processing status of a knowledge base. Typically used by callback handlers.",
)
async def update_knowledge_base_status(
    kb_id: int,
    status_update: KnowledgeBaseStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update knowledge base status"""
    kb_service = KnowledgeBaseService(db)
    kb = kb_service.get_knowledge_base_by_id(kb_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    # Only admin or the owner can update status
    if current_user.user_type.value != "admin" and kb.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this knowledge base status",
        )

    updated_kb = kb_service.update_status(kb_id, status_update.status)
    return updated_kb
