from typing import List, Optional, Tuple
from uuid import uuid4
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.knowledge_base import KnowledgeBase


class KnowledgeBaseService:
    """Service for CRUD operations on Knowledge Base"""

    @staticmethod
    def create_knowledge_base(
        db: Session,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        extra_data: Optional[dict] = None,
        service_id: Optional[int] = None,
        id: Optional[str] = None,
    ) -> KnowledgeBase:
        """Create a new knowledge base entry."""
        kb = KnowledgeBase(
            id=id or str(uuid4()),
            user_id=user_id,
            title=title,
            description=description,
            extra_data=extra_data,
            service_id=service_id,
            active=True,
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        return kb

    @staticmethod
    def get_knowledge_base_by_id(
        db: Session, kb_id: str
    ) -> Optional[KnowledgeBase]:
        """Get a single knowledge base by ID."""
        return (
            db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        )

    @staticmethod
    def get_knowledge_bases(
        db: Session,
        user_id: Optional[int] = None,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
    ) -> Tuple[List[KnowledgeBase], int]:
        """
        Get paginated list of knowledge bases.
        - If user_id is provided, returns only that user's KBs.
        - If user_id is None (admin), returns all KBs.
        """
        query = db.query(KnowledgeBase)

        if user_id is not None:
            query = query.filter(KnowledgeBase.user_id == user_id)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    KnowledgeBase.title.ilike(search_term),
                    KnowledgeBase.description.ilike(search_term),
                )
            )

        total = query.count()
        knowledge_bases = (
            query.order_by(KnowledgeBase.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        return knowledge_bases, total

    @staticmethod
    def update_knowledge_base(
        db: Session,
        kb_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        extra_data: Optional[dict] = None,
        active: Optional[bool] = None,
    ) -> Optional[KnowledgeBase]:
        """Update an existing knowledge base."""
        kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
        if not kb:
            return None

        if title is not None:
            kb.title = title
        if description is not None:
            kb.description = description
        if extra_data is not None:
            kb.extra_data = extra_data
        if active is not None:
            kb.active = active

        db.commit()
        db.refresh(kb)
        return kb

    @staticmethod
    def delete_knowledge_base(db: Session, kb_id: str) -> bool:
        """Delete a knowledge base."""
        kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
        if not kb:
            return False

        try:
            db.delete(kb)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
