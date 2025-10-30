import logging
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db
from models.user import User
from models.playground_message import (
    PlaygroundMessage,
    PlaygroundMessageRole,
    PlaygroundMessageStatus,
)
from services.external_ai_service import ExternalAIService
from services.service_token_service import ServiceTokenService
from schemas.callback import MessageType
from utils.auth_dependencies import admin_required

router = APIRouter(prefix="/admin/playground", tags=["admin-playground"])
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Schemas
# ============================================================================


class ActiveServiceResponse(BaseModel):
    service_name: str
    chat_url: str
    is_active: bool
    has_valid_token: bool


class DefaultPromptResponse(BaseModel):
    default_prompt: Optional[str]


class PlaygroundMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    job_id: Optional[str]
    status: Optional[str]
    custom_prompt: Optional[str]
    service_used: Optional[str]
    response_time_ms: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = Field(
        None,
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12}$"
        ),
    )
    custom_prompt: Optional[str] = Field(None, max_length=10000)


class ChatResponse(BaseModel):
    session_id: str
    user_message: PlaygroundMessageResponse
    assistant_message: PlaygroundMessageResponse
    job_id: str
    status: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: List[PlaygroundMessageResponse]
    total_count: int


class SessionSummary(BaseModel):
    session_id: str
    message_count: int
    created_at: datetime
    last_message_at: datetime


class SessionsResponse(BaseModel):
    sessions: List[SessionSummary]
    total_count: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/active-service", response_model=ActiveServiceResponse)
def get_active_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """
    Get active service configuration (Admin only).
    Returns information about the currently active AI service.
    """
    token = ServiceTokenService.get_active_token(db)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active service configured",
        )

    return ActiveServiceResponse(
        service_name=token.service_name,
        chat_url=token.chat_url or "",
        is_active=token.active == 1,
        has_valid_token=bool(token.access_token),
    )


@router.get("/default-prompt", response_model=DefaultPromptResponse)
def get_default_prompt(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """
    Get the current default prompt from service configuration (Admin only).
    """
    token = ServiceTokenService.get_active_token(db)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active service configured",
        )

    return DefaultPromptResponse(default_prompt=token.default_prompt)


@router.post("/chat", response_model=ChatResponse)
async def send_chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """
    Send a chat message to AI service with optional custom prompt (Admin only).
    Returns immediately with job_id. AI response arrives via WebSocket.
    """
    # Generate or validate session_id
    session_id = request.session_id or str(uuid.uuid4())

    # Get active service
    ai_service = ExternalAIService(db)
    if not ai_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active AI service configured",
        )

    # Store user message
    user_message = PlaygroundMessage(
        admin_user_id=current_user.id,
        session_id=session_id,
        role=PlaygroundMessageRole.USER,
        content=request.message,
        job_id=None,
        status=None,
        custom_prompt=request.custom_prompt,
        service_used=ai_service.token.service_name
        if ai_service.token
        else None,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    logger.info(
        f"Created playground user message {user_message.id} "
        f"for admin {current_user.id} (session: {session_id})"
    )

    # Create AI job with playground flag
    prompt = (
        request.custom_prompt
        if request.custom_prompt
        else (ai_service.token.default_prompt if ai_service.token else None)
    )

    try:
        # Prepare playground-specific callback params
        playground_callback_params = {
            "source": "playground",
            "session_id": session_id,
            "admin_user_id": current_user.id,
        }

        job_response = await ai_service.create_chat_job(
            message_id=user_message.id,  # Use user message ID
            message_type=MessageType.REPLY.value,  # For playground
            customer_id=0,  # Not applicable for playground
            chats=[{"role": "user", "content": request.message}],
            prompt=prompt,
            trace_id=f"playground_{session_id}_{user_message.id}",
            additional_callback_params=playground_callback_params,
        )

        if not job_response or "job_id" not in job_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create AI job",
            )

        job_id = job_response["job_id"]

        # Store pending assistant message
        assistant_message = PlaygroundMessage(
            admin_user_id=current_user.id,
            session_id=session_id,
            role=PlaygroundMessageRole.ASSISTANT,
            content="",  # Will be filled by callback
            job_id=job_id,
            status=PlaygroundMessageStatus.PENDING,
            custom_prompt=request.custom_prompt,
            service_used=ai_service.token.service_name
            if ai_service.token
            else None,
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        logger.info(
            f"Created AI job {job_id} for playground message "
            f"(session: {session_id}, assistant_msg: {assistant_message.id})"
        )

        return ChatResponse(
            session_id=session_id,
            user_message=PlaygroundMessageResponse.model_validate(
                user_message
            ),
            assistant_message=PlaygroundMessageResponse.model_validate(
                assistant_message
            ),
            job_id=job_id,
            status="pending",
        )

    except Exception as e:
        logger.error(f"Failed to create playground AI job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create AI job: {str(e)}",
        )


@router.get("/history", response_model=HistoryResponse)
def get_chat_history(
    session_id: str = Query(..., description="UUID of the playground session"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """
    Get chat history for a specific session (Admin only).
    Only returns messages belonging to the authenticated admin user.
    """
    # Get messages for this session and admin user
    messages_query = (
        db.query(PlaygroundMessage)
        .filter(
            PlaygroundMessage.session_id == session_id,
            PlaygroundMessage.admin_user_id == current_user.id,
        )
        .order_by(PlaygroundMessage.created_at)
    )

    total_count = messages_query.count()
    messages = messages_query.offset(offset).limit(limit).all()

    return HistoryResponse(
        session_id=session_id,
        messages=[
            PlaygroundMessageResponse.model_validate(msg) for msg in messages
        ],
        total_count=total_count,
    )


@router.get("/sessions", response_model=SessionsResponse)
def get_user_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """
    Get list of all playground sessions for authenticated admin (Admin only).
    """
    # Get session summaries
    sessions_query = (
        db.query(
            PlaygroundMessage.session_id,
            func.count(PlaygroundMessage.id).label("message_count"),
            func.min(PlaygroundMessage.created_at).label("created_at"),
            func.max(PlaygroundMessage.created_at).label("last_message_at"),
        )
        .filter(PlaygroundMessage.admin_user_id == current_user.id)
        .group_by(PlaygroundMessage.session_id)
        .order_by(desc("last_message_at"))
    )

    total_count = sessions_query.count()
    sessions_data = sessions_query.offset(offset).limit(limit).all()

    sessions = [
        SessionSummary(
            session_id=row.session_id,
            message_count=row.message_count,
            created_at=row.created_at,
            last_message_at=row.last_message_at,
        )
        for row in sessions_data
    ]

    return SessionsResponse(sessions=sessions, total_count=total_count)


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """
    Delete all messages in a playground session (Admin only).
    Can only delete own sessions.
    """
    # Verify session belongs to current user and get message count
    message_count = (
        db.query(PlaygroundMessage)
        .filter(
            PlaygroundMessage.session_id == session_id,
            PlaygroundMessage.admin_user_id == current_user.id,
        )
        .count()
    )

    if message_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or unauthorized",
        )

    # Delete all messages in the session
    db.query(PlaygroundMessage).filter(
        PlaygroundMessage.session_id == session_id,
        PlaygroundMessage.admin_user_id == current_user.id,
    ).delete()

    db.commit()

    logger.info(
        f"Deleted playground session {session_id} "
        f"({message_count} messages) for admin {current_user.id}"
    )

    return None
