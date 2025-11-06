from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserType
from schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)
from services.knowledge_base_service import KnowledgeBaseService
from services.service_token_service import ServiceTokenService
from services.external_ai_service import ExternalAIService
from utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/kb", tags=["knowledge_base"])

# TODO :: Add PATCH/PUT endpoints to update KB in RAG
# (currently only have to set default)


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Knowledge Base",
    description="Create a new knowledge base.",
)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Knowledge Base"""

    # check for active service token
    service_token = ServiceTokenService.get_active_token(db=db)
    if not service_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active service configured",
        )

    # Get active service
    ai_service = ExternalAIService(db)
    if not ai_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active AI service configured",
        )

    rag_kb_response = await ai_service.manage_knowledge_base(
        operation="create", name=kb_data.title, description=kb_data.description
    )

    if not rag_kb_response:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create knowledge base on external AI service.",
        )

    kb = KnowledgeBaseService.create_knowledge_base(
        db=db,
        id=str(rag_kb_response.get("knowledge_base_id")),
        user_id=current_user.id,
        title=kb_data.title,
        description=kb_data.description,
        extra_data=kb_data.extra_data,
        service_id=service_token.id,
    )
    return kb


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Knowledge Bases",
)
async def list_knowledge_bases(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Records per page"),
    search: Optional[str] = Query(None, description="Search term"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paginated list of knowledge bases"""
    user_id = (
        None
        if current_user.user_type.value == UserType.ADMIN.value
        else current_user.id
    )

    knowledge_bases, total = KnowledgeBaseService.get_knowledge_bases(
        db=db,
        user_id=user_id,
        page=page,
        size=size,
        search=search,
    )

    return KnowledgeBaseListResponse(
        data=knowledge_bases,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Knowledge Base by ID",
)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single knowledge base by ID"""
    kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    if (
        current_user.user_type.value != "admin"
        and kb.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this KB.",
        )

    return kb


@router.put(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Knowledge Base",
)
async def update_knowledge_base(
    kb_id: str,
    kb_update: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing knowledge base"""
    kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    if (
        current_user.user_type.value != "admin"
        and kb.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this KB.",
        )

    updated_kb = KnowledgeBaseService.update_knowledge_base(
        db=db,
        kb_id=kb_id,
        title=kb_update.title,
        description=kb_update.description,
        extra_data=kb_update.extra_data,
        active=kb_update.active,
    )

    return updated_kb


@router.delete(
    "/{kb_id}",
    summary="Delete Knowledge Base",
)
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    if (
        current_user.user_type.value != UserType.ADMIN.value
        and kb.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this KB.",
        )

    deleted = KnowledgeBaseService.delete_knowledge_base(db, kb_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge base.",
        )

    return {"message": "Knowledge base deleted successfully."}
