from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models.document import Document
from schemas.callback import CallbackStage


class DocumentService:
    """Service for CRUD operations on Documents"""

    @staticmethod
    def create_document(
        db: Session,
        kb_id: str,
        user_id: int,
        filename: str,
        file_path: Optional[str] = None,
        content_type: Optional[str] = None,
        file_size: Optional[int] = None,
        extra_data: Optional[dict] = None,
    ) -> Document:
        """Create a new document entry."""
        document = Document(
            kb_id=kb_id,
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            content_type=content_type,
            file_size=file_size,
            extra_data=extra_data,
            status=CallbackStage.QUEUED,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def get_document_by_id(
        db: Session, document_id: int
    ) -> Optional[Document]:
        """Get a document by its ID."""
        return db.query(Document).filter(Document.id == document_id).first()

    @staticmethod
    def get_documents(
        db: Session,
        user_id: Optional[int] = None,
        kb_id: Optional[str] = None,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
    ) -> Tuple[List[Document], int]:
        """
        Get documents with optional filters:
        - user_id: only that user’s documents
        - kb_id: only documents for that KB
        - search: title/filename search
        Supports pagination.
        """
        query = db.query(Document)

        if user_id is not None:
            query = query.filter(Document.user_id == user_id)

        if kb_id is not None:
            query = query.filter(Document.kb_id == kb_id)

        if search:
            search_term = f"%{search}%"
            query = query.filter(or_(Document.filename.ilike(search_term)))

        total = query.count()
        documents = (
            query.order_by(Document.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        return documents, total

    @staticmethod
    def update_document(
        db: Session,
        document_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        extra_data: Optional[dict] = None,
    ) -> Optional[Document]:
        """Update document metadata."""
        document = DocumentService.get_document_by_id(db, document_id)
        if not document:
            return None

        # Title/description are optional, may not exist in model
        if hasattr(document, "title") and title is not None:
            document.title = title
        if hasattr(document, "description") and description is not None:
            document.description = description
        if extra_data is not None:
            document.extra_data = extra_data

        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def update_document_status(
        db: Session,
        document_id: int,
        status: CallbackStage,
        external_id: str,
        job_id: str,
    ) -> Optional[Document]:
        """Update a document’s status."""
        doc = DocumentService.get_document_by_id(db, document_id)
        if not doc:
            return None

        doc.status = status
        doc.external_id = external_id
        doc.job_id = job_id

        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def delete_document(db: Session, document_id: int) -> bool:
        """Delete a document."""
        doc = DocumentService.get_document_by_id(db, document_id)
        if not doc:
            return False

        db.delete(doc)
        db.commit()
        return True
