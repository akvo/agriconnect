from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models.message import Message, MessageFrom, MessageStatus
from models.ticket import Ticket
from models.user import User, UserType
from models.administrative import UserAdministrative
from utils.auth_dependencies import get_current_user
from services.whatsapp_service import WhatsAppService
from services.socketio_service import (
    emit_message_received,
    emit_ticket_resolved
)

router = APIRouter(prefix="/messages", tags=["messages"])


# Schemas
class MessageStatusUpdate(BaseModel):
    status: int


class MessageCreate(BaseModel):
    ticket_id: int
    body: str
    # MessageFrom.USER, MessageFrom.CUSTOMER, or MessageFrom.LLM
    from_source: int


class MessageResponse(BaseModel):
    id: int
    ticket_id: int
    customer_id: int
    user_id: Optional[int]
    body: str
    from_source: int
    status: int
    message_sid: str
    created_at: datetime


def _check_message_access(message: Message, user: User, db: Session) -> None:
    """Check if user has access to update the message. Raises 403 if not."""
    # Get the ticket associated with this message
    ticket = (
        db.query(Ticket)
        .filter(Ticket.message_id == message.id)
        .first()
    )

    if not ticket:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found for this message",
        )

    if user.user_type == UserType.ADMIN:
        # Admin has access to all messages
        return

    # User can only access messages in their assigned administrative areas
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )
    admin_ids = [ua.administrative_id for ua in user_admins]

    if ticket.administrative_id not in admin_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have access to messages"
                " outside your administrative area"
            ),
        )


@router.patch("/{message_id}/status", response_model=MessageResponse)
async def update_message_status(
    message_id: int,
    status_update: MessageStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the status of a message.

    Allowed status transitions:
    - pending → replied (when User sends reply)
    - replied → resolved (when ticket is closed)
    - pending → resolved (if no reply needed)

    When status = 'resolved', both message status and ticket.resolved_at
    are updated atomically.
    """
    # Validate status value
    valid_statuses = [
        MessageStatus.PENDING,
        MessageStatus.REPLIED,
        MessageStatus.RESOLVED,
    ]
    if status_update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    # Get message
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check access
    _check_message_access(message, current_user, db)

    # Get associated ticket
    ticket = (
        db.query(Ticket)
        .filter(Ticket.message_id == message.id)
        .first()
    )

    # Update message status
    message.status = status_update.status

    # If resolving, also update ticket.resolved_at atomically
    if status_update.status == MessageStatus.RESOLVED and ticket:
        ticket.resolved_at = datetime.now(timezone.utc)
        ticket.resolved_by = current_user.id

    db.commit()
    db.refresh(message)

    # Emit WebSocket events
    if ticket:

        # If resolved, also emit ticket resolved event
        if status_update.status == MessageStatus.RESOLVED:
            await emit_ticket_resolved(
                ticket_id=ticket.id,
                resolved_at=ticket.resolved_at.isoformat(),
                administrative_id=ticket.administrative_id,
            )

    return MessageResponse(
        id=message.id,
        ticket_id=ticket.id if ticket else None,
        customer_id=message.customer_id,
        user_id=message.user_id,
        body=message.body,
        from_source=message.from_source,
        status=message.status,
        message_sid=message.message_sid,
        created_at=message.created_at,
    )


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new message (User reply).

    When a User sends a reply to an escalated message:
    1. Creates new message with from_source=MessageFrom.USER
    2. Automatically updates escalated message status to "replied"
    3. Emits WebSocket events for real-time updates
    """
    # Get ticket
    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == message_data.ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check access
    if current_user.user_type != UserType.ADMIN:
        user_admins = (
            db.query(UserAdministrative)
            .filter(UserAdministrative.user_id == current_user.id)
            .all()
        )
        admin_ids = [ua.administrative_id for ua in user_admins]

        if ticket.administrative_id not in admin_ids:
            raise HTTPException(
                status_code=403,
                detail=(
                    "You do not have access to reply to tickets"
                    " outside your administrative area"
                ),
            )

    # Validate from_source and set user_id
    if message_data.from_source == MessageFrom.CUSTOMER:
        user_id = None
    elif message_data.from_source == MessageFrom.USER:
        user_id = current_user.id
    elif message_data.from_source == MessageFrom.LLM:
        user_id = None  # LLM messages don't have a user_id
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid from_source. Must be one of: "
                f"{MessageFrom.CUSTOMER}, {MessageFrom.USER}, "
                f"{MessageFrom.LLM}"
            ),
        )

    # Create new message
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    new_message = Message(
        message_sid=f"USER_{current_user.id}_{timestamp_ms}",
        customer_id=ticket.customer_id,
        user_id=user_id,
        body=message_data.body,
        from_source=message_data.from_source,
        status=MessageStatus.PENDING,  # New messages start as pending
    )

    db.add(new_message)
    db.flush()  # Get the ID without committing

    # If this is a User reply, update escalated message status to "replied"
    if message_data.from_source == MessageFrom.USER and ticket.message:
        escalated_message = ticket.message
        if escalated_message.status == MessageStatus.PENDING:
            escalated_message.status = MessageStatus.REPLIED

    db.commit()
    db.refresh(new_message)

    # Send WhatsApp message to customer when User replies
    if message_data.from_source == MessageFrom.USER:
        try:
            # Get customer phone number from ticket
            customer_phone = ticket.customer.phone_number

            # Send WhatsApp message
            whatsapp_service = WhatsAppService()
            response = whatsapp_service.send_message(
                to_number=customer_phone,
                message_body=new_message.body,
            )

            print(
                f"WhatsApp reply sent to {customer_phone}: "
                f"{response.get('sid')}"
            )

            # Optional: Update message_sid with Twilio SID for tracking
            # This helps correlate backend messages with Twilio messages
            if response.get("sid"):
                new_message.message_sid = response.get("sid")
                db.commit()
                db.refresh(new_message)

        except Exception as e:
            # Log error but don't fail the request
            # Message is already saved in DB and can be retried later
            print(f"Failed to send WhatsApp reply: {e}")
            # TODO: Implement retry queue or dead letter queue for failed sends

    # Emit WebSocket event for new message
    sender_id = (
        current_user.id
        if message_data.from_source == MessageFrom.USER
        else None
    )
    customer_name = ticket.customer.phone_number
    if ticket.customer.full_name:
        customer_name = ticket.customer.full_name
    await emit_message_received(
        ticket_id=ticket.id,
        message_id=new_message.id,
        message_sid=new_message.message_sid,
        customer_id=ticket.customer_id,
        body=new_message.body,
        from_source=message_data.from_source,
        ts=new_message.created_at.isoformat(),
        administrative_id=ticket.administrative_id,
        ticket_number=ticket.ticket_number,
        customer_name=customer_name,
        sender_user_id=sender_id,
    )

    return MessageResponse(
        id=new_message.id,
        ticket_id=ticket.id,
        customer_id=new_message.customer_id,
        user_id=new_message.user_id,
        body=new_message.body,
        from_source=new_message.from_source,
        status=new_message.status,
        message_sid=new_message.message_sid,
        created_at=new_message.created_at,
    )
