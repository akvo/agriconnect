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
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
)
from services.document_service import DocumentService
from utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new Document",
    description="Upload a single file to be added to a Knowledge Base.",
)
async def create_document(
    file: UploadFile = File(..., description="Document file to upload"),
    kb_id: str = Form(
        ..., description="Knowledge Base ID this document belongs to"
    ),
    title: str = Form(..., description="Title of the document"),
    description: Optional[str] = Form(
        None, description="Optional document description"
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

    try:
        document = DocumentService.create_document(
            db=db,
            user_id=current_user.id,
            kb_id=kb_id,
            filename=file.filename,
            content_type=file.content_type,
            file_size=getattr(file, "size", None),
            extra_data={
                "title": title,
                "description": description,
            },
        )
        return document

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
    user_id = (
        None if current_user.user_type.value == "admin" else current_user.id
    )

    documents, total = DocumentService.get_documents(
        db=db,
        user_id=user_id,
        kb_id=kb_id,
        page=page,
        size=size,
        search=search,
    )

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document by ID",
    description="Retrieve a document by its ID.",
)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = DocumentService.get_document_by_id(db, document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if (
        current_user.user_type.value != "admin"
        and document.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document.",
        )

    return document


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Document Metadata",
)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = DocumentService.get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if (
        current_user.user_type.value != "admin"
        and document.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this document.",
        )

    updated_doc = DocumentService.update_document(
        db=db,
        document_id=document_id,
        extra_data=document_update.extra_data,
    )

    return updated_doc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Document",
    description="Delete a document. Only admins or owners can delete.",
)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = DocumentService.get_document_by_id(db, document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if (
        current_user.user_type.value != "admin"
        and document.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document.",
        )

    success = DocumentService.delete_document(db, document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document.",
        )

    return None
