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
    CreateKnowledgeBaseResponse,
)
from services.knowledge_base_service import KnowledgeBaseService
from services.service_token_service import ServiceTokenService
from services.external_ai_service import ExternalAIService
from utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/kb", tags=["knowledge_base"])


@router.post(
    "",
    response_model=CreateKnowledgeBaseResponse,
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
        external_id=str(rag_kb_response.get("knowledge_base_id")),
        user_id=current_user.id,
        service_id=service_token.id,
    )
    return CreateKnowledgeBaseResponse(
        id=kb.id,
        user_id=kb.user_id,
        title=rag_kb_response.get("name"),
        description=rag_kb_response.get("description"),
    )


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

    knowledge_bases = KnowledgeBaseService.get_knowledge_bases(
        db=db,
        user_id=user_id,
    )
    kb_external_ids = {kb.external_id: kb.id for kb in knowledge_bases}

    # TODO::Need to make RAG accept list of kb_ids
    rag_kb_response = await ai_service.manage_knowledge_base(operation="list")

    # empty
    if not rag_kb_response.get("total"):
        return KnowledgeBaseListResponse(
            data=[],
            total=0,
            page=0,
            size=0,
        )

    data = []
    for kb in rag_kb_response.get("data"):
        kb_id = kb.get("id")
        kb_id = str(kb_id) if kb_id else None
        if not kb_id or kb_id not in kb_external_ids.keys():
            continue
        current_kb_id = kb_external_ids.get(str(kb_id))
        data.append(
            KnowledgeBaseResponse(
                id=current_kb_id,
                title=kb.get("name"),
                description=kb.get("description"),
                created_at=kb.get("created_at"),
                updated_at=kb.get("updated_at"),
            ),
        )

    return KnowledgeBaseListResponse(
        data=data or [],
        total=rag_kb_response.get("total", 0),
        page=rag_kb_response.get("page", 0),
        size=rag_kb_response.get("size", 0),
    )


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Knowledge Base by ID",
)
async def get_knowledge_base(
    kb_id: int,
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
        operation="get", kb_id=kb.external_id
    )

    return KnowledgeBaseResponse(
        id=kb_id,
        title=rag_kb_response.get("name"),
        description=rag_kb_response.get("description"),
        created_at=rag_kb_response.get("created_at"),
        updated_at=rag_kb_response.get("updated_at"),
    )


@router.put(
    "/{kb_id}",
    response_model=CreateKnowledgeBaseResponse,
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

    # Get active service
    ai_service = ExternalAIService(db)
    rag_kb_response = await ai_service.manage_knowledge_base(
        operation="update",
        name=kb_update.title,
        description=kb_update.description,
        kb_id=kb.external_id,
    )

    if not rag_kb_response:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to update knowledge base on external AI service.",
        )

    return CreateKnowledgeBaseResponse(
        id=kb_id,
        user_id=kb.user_id,
        title=rag_kb_response.get("name"),
        description=rag_kb_response.get("description"),
    )


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

    # Get active service
    ai_service = ExternalAIService(db)
    rag_kb_response = await ai_service.manage_knowledge_base(
        operation="delete",
        kb_id=kb.external_id,
    )

    if not rag_kb_response:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to delete knowledge base on external AI service.",
        )

    deleted = KnowledgeBaseService.delete_knowledge_base(db, kb_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge base.",
        )

    return {"message": "Knowledge base deleted successfully."}
