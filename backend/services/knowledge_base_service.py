from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session
from models.knowledge_base import KnowledgeBase
from schemas.callback import CallbackStage


class KnowledgeBaseService:
    def __init__(self, db: Session):
        self.db = db

    def create_knowledge_base(
        self,
        user_id: int,
        filename: str,
        title: str,
        description: str = None,
        extra_data: dict = None,
    ) -> KnowledgeBase:
        """Create a new knowledge base entry."""
        kb = KnowledgeBase(
            user_id=user_id,
            filename=filename,
            title=title,
            description=description,
            extra_data=extra_data,
            status=CallbackStage.QUEUED,
        )
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def get_knowledge_base_by_id(self, kb_id: int) -> Optional[KnowledgeBase]:
        """Get knowledge base by ID."""
        return (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.id == kb_id)
            .first()
        )

    def get_user_knowledge_bases(
        self,
        user_id: int,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
    ) -> Tuple[List[KnowledgeBase], int]:
        """Get all knowledge bases for a user with pagination and search."""
        query = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id
        )

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    KnowledgeBase.title.ilike(search_term),
                    KnowledgeBase.filename.ilike(search_term),
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

    def get_all_knowledge_bases(
        self, page: int = 1, size: int = 10, search: Optional[str] = None
    ) -> Tuple[List[KnowledgeBase], int]:
        """Get all knowledge bases with pagination and search."""
        query = self.db.query(KnowledgeBase)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    KnowledgeBase.title.ilike(search_term),
                    KnowledgeBase.filename.ilike(search_term),
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

    def update_knowledge_base(
        self,
        kb_id: int,
        title: str = None,
        description: str = None,
        extra_data: dict = None,
        status: CallbackStage = None,
    ) -> Optional[KnowledgeBase]:
        """Update an existing knowledge base."""
        kb = self.get_knowledge_base_by_id(kb_id)
        if not kb:
            return None

        if title is not None:
            kb.title = title
        if description is not None:
            kb.description = description
        if extra_data is not None:
            kb.extra_data = extra_data
        if status is not None:
            kb.status = status

        self.db.commit()
        self.db.refresh(kb)
        return kb

    def delete_knowledge_base(self, kb_id: int) -> bool:
        """Delete a knowledge base."""
        kb = self.get_knowledge_base_by_id(kb_id)
        if not kb:
            return False

        self.db.delete(kb)
        self.db.commit()
        return True

    def update_status(
        self, kb_id: int, status: CallbackStage
    ) -> Optional[KnowledgeBase]:
        """Update only the status of a knowledge base."""
        kb = self.get_knowledge_base_by_id(kb_id)
        if not kb:
            return None

        kb.status = status
        self.db.commit()
        self.db.refresh(kb)
        return kb
