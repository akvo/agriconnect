import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional, List

from database import get_db
from models.message import Message, MessageFrom, MessageStatus, MediaType
from models.ticket import Ticket
from models.user import User, UserType
from models.administrative import UserAdministrative
from utils.auth_dependencies import get_current_user
from services.administrative_service import AdministrativeService
from services.whatsapp_service import WhatsAppService
from services.socketio_service import (
    emit_message_received,
    emit_ticket_resolved
)

router = APIRouter(prefix="/messages", tags=["messages"])


def _get_user_administrative_ids(user: User, db: Session) -> List[int]:
    """Get list of administrative IDs accessible by the user.

    For upper-level EOs (assigned to region/district), this returns
    all descendant ward IDs so they can access messages in subordinate areas.
    """
    if user.user_type == UserType.ADMIN:
        # Admin can access all messages
        return []

    # EO can access messages in their assigned areas and all descendant wards
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )

    # Collect all accessible ward IDs (including descendants)
    all_ward_ids = set()
    for ua in user_admins:
        # Add the assigned area itself
        all_ward_ids.add(ua.administrative_id)
        # Add all descendant wards
        descendant_ids = AdministrativeService.get_descendant_ward_ids(
            db, ua.administrative_id
        )
        all_ward_ids.update(descendant_ids)

    return list(all_ward_ids)


# Schemas
class MessageStatusUpdate(BaseModel):
    status: int


class MessageCreate(BaseModel):
    ticket_id: int
    body: str
    # MessageFrom.USER, MessageFrom.CUSTOMER, or MessageFrom.LLM
    from_source: int
    # Optional media fields for image messages
    media_url: Optional[str] = None  # Relative path like /media/abc.jpg
    media_type: Optional[str] = "TEXT"  # TEXT, IMAGE, etc.


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
    media_url: Optional[str] = None
    media_type: str = "TEXT"


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

    # EO can only access messages in their administrative area
    # (including descendant wards for upper-level officers)
    admin_ids = _get_user_administrative_ids(user, db)
    if ticket.administrative_id not in admin_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have access to messages"
                " outside your administrative area"
            ),
        )


# Allowed image types for upload
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
# Max file size: 16MB (Twilio limit for WhatsApp media)
MAX_IMAGE_SIZE = 16 * 1024 * 1024


@router.post("/upload-image")
async def upload_message_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image for sending via WhatsApp.

    Validates image type and size, saves to /media directory,
    and returns the media URL for use in message creation.

    Supported formats: jpeg, png, webp, gif
    Max file size: 16MB (Twilio WhatsApp limit)

    Returns:
        {"media_url": "/media/{filename}", "media_type": "IMAGE"}
    """
    # Validate content type
    content_type = file.content_type
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid image type: {content_type}. "
                f"Allowed types: {list(ALLOWED_IMAGE_TYPES.keys())}"
            ),
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Image too large: {len(content) / (1024 * 1024):.2f}MB. "
                f"Max size: 16MB"
            ),
        )

    # Generate unique filename
    extension = ALLOWED_IMAGE_TYPES[content_type]
    filename = f"{uuid.uuid4().hex}.{extension}"

    # Ensure media directory exists
    media_dir = "media"
    os.makedirs(media_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(media_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "media_url": f"/media/{filename}",
        "media_type": "IMAGE",
    }


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
                resolved_by=current_user.full_name,
            )

    # Get media_type value as string
    msg_media_type = (
        message.media_type.value
        if message.media_type
        else "TEXT"
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
        media_url=message.media_url,
        media_type=msg_media_type,
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

    # Check access (including descendant wards for upper-level officers)
    if current_user.user_type != UserType.ADMIN:
        admin_ids = _get_user_administrative_ids(current_user, db)

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

    # Determine media_type enum value
    media_type_enum = MediaType.TEXT
    if message_data.media_type and message_data.media_type != "TEXT":
        try:
            media_type_enum = MediaType[message_data.media_type]
        except KeyError:
            pass  # Default to TEXT if invalid

    new_message = Message(
        message_sid=f"USER_{current_user.id}_{timestamp_ms}",
        customer_id=ticket.customer_id,
        user_id=user_id,
        body=message_data.body,
        from_source=message_data.from_source,
        status=MessageStatus.PENDING,  # New messages start as pending
        media_url=message_data.media_url,
        media_type=media_type_enum,
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

            # Format message with EO's name below in italic (not stored in DB)
            formatted_body = (
                f"{new_message.body}\n\n— _{current_user.full_name}_"
            )

            # Check if this is a media message
            if message_data.media_url and message_data.media_type == "IMAGE":
                # Build full public URL for the media
                web_domain = os.getenv("WEBDOMAIN", "http://localhost:8000")
                full_media_url = f"{web_domain}{message_data.media_url}"

                response = whatsapp_service.send_message_with_media(
                    to_number=customer_phone,
                    message_body=formatted_body,
                    media_url=full_media_url,
                )
                print(
                    f"WhatsApp image sent to {customer_phone}: "
                    f"{response.get('sid')} (media: {full_media_url})"
                )
            else:
                response = whatsapp_service.send_message(
                    to_number=customer_phone,
                    message_body=formatted_body,
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

    # Set sender_name based on message source
    if message_data.from_source == MessageFrom.USER:
        # For admin/EO messages, use sender's full name
        sender_name = current_user.full_name
    else:
        # For customer messages, use customer's name or phone
        sender_name = ticket.customer.phone_number
        if ticket.customer.full_name:
            sender_name = ticket.customer.full_name
    await emit_message_received(
        ticket_id=ticket.id,
        message_id=new_message.id,
        phone_number=ticket.customer.phone_number,
        body=new_message.body,
        from_source=message_data.from_source,
        ts=new_message.created_at.isoformat(),
        administrative_id=ticket.administrative_id,
        ticket_number=ticket.ticket_number,
        sender_name=sender_name,
        sender_user_id=sender_id,
        customer_id=ticket.customer_id,
    )

    # Get media_type value as string
    media_type_value = (
        new_message.media_type.value
        if new_message.media_type
        else "TEXT"
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
        media_url=new_message.media_url,
        media_type=media_type_value,
    )
