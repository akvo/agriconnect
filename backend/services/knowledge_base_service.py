from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from models.knowledge_base import KnowledgeBase


class KnowledgeBaseService:
    """Service for CRUD operations on Knowledge Base"""

    @staticmethod
    def create_knowledge_base(
        db: Session,
        user_id: int,
        external_id: str,
        service_id: int,
        is_active: Optional[bool] = False,
    ) -> KnowledgeBase:
        """Create a new knowledge base entry."""
        kb = KnowledgeBase(
            user_id=user_id,
            external_id=external_id,
            service_id=service_id,
            is_active=is_active,
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
    ) -> Tuple[List[KnowledgeBase], int]:
        """
        Get list of knowledge bases.
        - If user_id is provided, returns only that user's KBs.
        - If user_id is None (admin), returns all KBs.
        - Filter for kb that only have external_id
        """
        query = db.query(KnowledgeBase).filter(
            KnowledgeBase.external_id.isnot(None)
        )

        if user_id is not None:
            query = query.filter(KnowledgeBase.user_id == user_id)

        knowledge_bases = query.order_by(KnowledgeBase.created_at.desc()).all()

        return knowledge_bases

    @staticmethod
    def get_active_knowledge_bases(
        db: Session,
    ) -> Tuple[List[KnowledgeBase], int]:
        """Get a active knowledge bases."""
        return (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.is_active.is_(True))
            .all()
        )

    @staticmethod
    def update_knowledge_base(
        db: Session,
        kb_id: int,
        is_active: Optional[bool] = None,
    ) -> Optional[KnowledgeBase]:
        """Update fields of a knowledge base."""
        kb = KnowledgeBaseService.get_knowledge_base_by_id(db, kb_id)
        if not kb:
            return None

        if is_active is not None:
            kb.is_active = is_active

        try:
            db.commit()
            db.refresh(kb)
            return kb
        except Exception:
            db.rollback()
            return None

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
