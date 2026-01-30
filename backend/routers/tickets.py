import asyncio
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from datetime import datetime, timezone

from database import get_db
from models.ticket import Ticket
from models.customer import Customer
from models.message import Message, MessageFrom
from schemas.callback import MessageType
from models.user import User, UserType
from models.administrative import UserAdministrative, Administrative
from schemas.ticket import (
    TicketCreate,
    TicketListResponse,
    TicketResponse,
    TicketMessagesResponse,
    TicketStatus,
)
from utils.auth_dependencies import get_current_user
from services.socketio_service import emit_ticket_resolved
from services.tagging_service import classify_ticket, get_tag_name

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _get_user_administrative_ids(user: User, db: Session) -> List[int]:
    """Get list of administrative IDs accessible by the user."""
    if user.user_type == UserType.ADMIN:
        # Admin can access all tickets
        return []

    # EO can only access tickets in their assigned administrative areas
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )

    return [ua.administrative_id for ua in user_admins]


def _check_ticket_access(ticket: Ticket, user: User, db: Session) -> None:
    """Check if user has access to the ticket. Raises 403 if not."""
    if user.user_type == UserType.ADMIN:
        # Admin has access to all tickets
        return

    # EO can only access tickets in their administrative area
    admin_ids = _get_user_administrative_ids(user, db)
    if ticket.administrative_id not in admin_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have access to tickets"
                " outside your administrative area"
            ),
        )


def _serialize_ticket(
    ticket: Ticket, db: Session = None,
) -> dict:
    resolver = None
    if ticket.resolved_by:
        # lazy load resolver
        resolver_obj = ticket.resolver
        resolver = (
            {
                "id": resolver_obj.id,
                "name": resolver_obj.full_name,
                "phone_number": resolver_obj.phone_number,
                "email": resolver_obj.email,
                "user_type": resolver_obj.user_type,
            } if resolver_obj else None
        )

    customer = ticket.customer
    message = ticket.message
    context_message = ticket.context_message

    ward = None
    if (
        hasattr(customer, "customer_administrative")
        and len(customer.customer_administrative) > 0
    ):
        admin = customer.customer_administrative[0].administrative
        ward = admin.path
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "customer": (
            {
                "id": customer.id,
                "name": customer.full_name,
                "phone_number": customer.phone_number,
                "crop_type": customer.crop_type,
                "gender": customer.gender,
                "age": customer.age,
                "language": customer.language,
                "ward": ward,
            }
            if customer
            else None
        ),
        "message": (
            {
                "id": message.id,
                "body": message.body,
                "message_sid": message.message_sid,
                "created_at": message.created_at.isoformat()
            } if message else None
        ),
        "context_message": (
            {
                "id": context_message.id,
                "body": context_message.body,
                "message_sid": context_message.message_sid,
                "created_at": context_message.created_at.isoformat()
            } if context_message else None
        ),
        "status": "resolved" if ticket.resolved_at else "open",
        "created_at": ticket.created_at.isoformat(),
        "resolved_at": (
            ticket.resolved_at.isoformat() if ticket.resolved_at else None
        ),
        "resolver": resolver,
        "tag": get_tag_name(ticket.tag) if ticket.tag else None,
        "tag_confidence": ticket.tag_confidence,
    }


@router.post(
    "/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED
)
async def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    """Create a ticket (no auth required)."""
    # Validate customer and message
    customer = (
        db.query(Customer).filter(Customer.id == payload.customer_id).first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    message = (
        db.query(Message).filter(Message.id == payload.message_id).first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Ensure message not already ticketed
    existing = db.query(Ticket).filter(Ticket.message_id == message.id).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Message already linked to a ticket"
        )

    # Get administrative_id from Administrative with national level = 1
    national_adm = (
        db.query(Administrative.id)
        .filter(Administrative.parent_id.is_(None))
        .first()
    )
    admin_id = national_adm.id
    if (
        hasattr(customer, "customer_administrative")
        and len(customer.customer_administrative) > 0
    ):
        admin_id = customer.customer_administrative[0].administrative_id

    now = datetime.now(timezone.utc)
    ticket_number = now.strftime("%Y%m%d%H%M%S")
    ticket = Ticket(
        ticket_number=ticket_number,
        administrative_id=admin_id,
        customer_id=customer.id,
        message_id=message.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"ticket": _serialize_ticket(ticket, db)}


@router.get("/", response_model=TicketListResponse)
async def list_tickets(
    status: Optional[TicketStatus] = Query(TicketStatus.OPEN),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List tickets with pagination and optional status filter.

    Admin users can see all tickets.
    EO users can only see tickets in their assigned administrative areas.

    Business rules:
    - For OPEN status: show only the earliest unresolved ticket per customer
    - For RESOLVED status: show ALL resolved tickets (no grouping)
    """
    # Get administrative IDs for EO users
    admin_ids = None
    if current_user.user_type == UserType.EXTENSION_OFFICER:
        admin_ids = _get_user_administrative_ids(current_user, db)
        if not admin_ids:
            # EO has no administrative assignments, return empty
            return {
                "tickets": [],
                "total": 0,
                "page": page,
                "size": page_size,
            }

    # For RESOLVED: show ALL resolved tickets (no grouping by customer)
    query = db.query(Ticket).filter(Ticket.resolved_at.isnot(None))

    # Filter by administrative area for EO users
    if admin_ids:
        query = query.filter(Ticket.administrative_id.in_(admin_ids))

    query = query.order_by(desc(Ticket.resolved_at))
    # Build query based on status
    if status == TicketStatus.OPEN:
        # For OPEN: show only earliest unresolved ticket per customer
        # Subquery to get MIN(id) per customer for open tickets
        subquery = (
            db.query(
                Ticket.customer_id,
                func.min(Ticket.id).label('selected_ticket_id')
            )
            .filter(Ticket.resolved_at.is_(None))
        )

        # Filter by administrative area for EO users
        if admin_ids is not None:
            subquery = subquery.filter(Ticket.administrative_id.in_(admin_ids))

        subquery = subquery.group_by(Ticket.customer_id).subquery()

        # Main query joins with subquery to get only the selected tickets
        query = (
            db.query(Ticket)
            .join(subquery, Ticket.id == subquery.c.selected_ticket_id)
        ).order_by(desc(Ticket.updated_at))

    # Get total count
    total = query.count()
    tickets = (
        query
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "tickets": [
            _serialize_ticket(t, db)
            for t in tickets
        ],
        "total": total,
        "page": page,
        "size": page_size,
    }


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket_header(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get ticket header information.

    Admin users can access any ticket.
    EO users can only access tickets in their assigned administrative areas.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check access for EO users
    _check_ticket_access(ticket, current_user, db)

    return {"ticket": _serialize_ticket(ticket)}


# Helper to convert from_source integer to string
def get_from_source_string(from_source: int) -> str:
    """Convert from_source integer to string representation.
    Uses MessageFrom constants:
    - CUSTOMER = 1 -> "whatsapp"
    - USER = 2 -> "system"
    - LLM = 3 -> "llm"
    """
    if from_source == MessageFrom.CUSTOMER:
        return "whatsapp"
    elif from_source == MessageFrom.USER:
        return "system"
    elif from_source == MessageFrom.LLM:
        return "llm"
    return "unknown"


@router.get("/{ticket_id}/messages", response_model=TicketMessagesResponse)
async def get_ticket_conversation(
    ticket_id: int,
    before_ts: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get ticket conversation messages.

    Returns messages from the ticket's escalation point onwards.
    - Without before_ts: messages from ticket.message_id to latest
    - With before_ts: older messages before that timestamp (pagination)

    Shows ALL messages in the ticket conversation
    (from customer, all users, and LLM)
    so that agents can see the full conversation history including messages
    from other agents.

    Admin users can access any ticket.
    EO users can only access tickets in their assigned administrative areas.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # Get next and previous tickets for the same customer
    next_ticket = (
        db.query(Ticket)
        .filter(
            Ticket.customer_id == ticket.customer_id,
            Ticket.id > ticket.id,
        )
        .order_by(Ticket.id.asc())
        .first()
    )
    previous_ticket = (
        db.query(Ticket)
        .filter(
            Ticket.customer_id == ticket.customer_id,
            Ticket.id < ticket.id,
        )
        .order_by(Ticket.id.desc())
        .first()
    )
    # Check access for EO users
    _check_ticket_access(ticket, current_user, db)

    # Get the ticket's base message to determine the starting point
    ticket_message = ticket.message

    # Get ALL messages for the ticket's customer
    # This includes:
    # 1. Messages from CUSTOMER (from_source = CUSTOMER)
    # 2. Messages from ALL users (from_source = USER)
    # 3. Messages from LLM (from_source = LLM)
    # This allows all agents to see the full conversation history
    # Exclude BROADCAST messages (e.g., weather broadcasts) from ticket view
    msgs_query = db.query(Message).filter(
        Message.customer_id == ticket.customer_id,
        or_(
            Message.message_type.is_(None),
            Message.message_type != MessageType.BROADCAST,
        ),
    )

    if before_ts:
        # Pagination: get older messages before the given timestamp and
        # Make sure we don't go before previous ticket's escalation message
        try:
            before_dt = datetime.fromisoformat(before_ts)
            msgs_query = msgs_query.filter(Message.created_at < before_dt)
            # Use previous ticket's message creation time as lower boundary
            if previous_ticket:
                previous_message = previous_ticket.message
                if previous_message and previous_message.created_at:
                    msgs_query = msgs_query.filter(
                        Message.created_at >= previous_message.created_at,
                    )
        except Exception:
            # ignore invalid before_ts, return from ticket start
            pass
    else:
        # Default: include context before ticket's escalation message
        # Look for FOLLOW_UP and the original question that triggered it
        start_time = None
        if ticket_message and ticket_message.created_at:
            # Look for the most recent FOLLOW_UP before (or at) ticket time
            follow_up_msg = (
                db.query(Message)
                .filter(
                    Message.customer_id == ticket.customer_id,
                    Message.message_type == MessageType.FOLLOW_UP,
                    Message.created_at <= ticket_message.created_at,
                )
                .order_by(Message.created_at.desc())
                .first()
            )

            if follow_up_msg:
                # Find the message just before FOLLOW_UP (original question)
                original_question = (
                    db.query(Message)
                    .filter(
                        Message.customer_id == ticket.customer_id,
                        Message.created_at < follow_up_msg.created_at,
                    )
                    .order_by(Message.created_at.desc())
                    .first()
                )
                if original_question:
                    start_time = original_question.created_at
                else:
                    start_time = follow_up_msg.created_at
            else:
                start_time = ticket_message.created_at

            # Respect previous ticket boundary
            if previous_ticket:
                prev_msg = previous_ticket.message
                if prev_msg and prev_msg.created_at:
                    if prev_msg.created_at > start_time:
                        start_time = prev_msg.created_at

            msgs_query = msgs_query.filter(Message.created_at >= start_time)

        # Use next ticket's message creation time as upper boundary
        # This ensures we stop BEFORE the next ticket's escalation message
        if next_ticket:
            next_message = next_ticket.message
            if next_message and next_message.created_at:
                msgs_query = msgs_query.filter(
                    Message.created_at < next_message.created_at,
                )

    msgs = msgs_query.order_by(Message.created_at.desc()).limit(limit).all()

    messages = [
        {
            "id": m.id,
            "message_sid": m.message_sid,
            "body": m.body,
            "from_source": get_from_source_string(m.from_source),
            "message_type": (
                getattr(m, "message_type", None).name
                if getattr(m, "message_type", None)
                else None
            ),
            "status": getattr(m, "status", None),
            "delivery_status": (
                m.delivery_status.value
                if hasattr(m, "delivery_status") and m.delivery_status
                else "PENDING"
            ),
            "user_id": m.user_id,
            "user": (
                {
                    "id": m.user.id,
                    "full_name": m.user.full_name,
                    "email": m.user.email,
                    "phone_number": m.user.phone_number,
                    "user_type": m.user.user_type,
                }
                if m.user_id and m.user
                else None
            ),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]

    return {
        "messages": messages,
        "total": len(messages),
        "before_ts": None,
        "limit": limit,
    }


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def mark_ticket_resolved(
    ticket_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a ticket as resolved.

    Admin users can resolve any ticket.
    EO users can only resolve tickets in their assigned administrative areas.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check access for EO users
    _check_ticket_access(ticket, current_user, db)

    if ticket.resolved_at is not None:
        raise HTTPException(status_code=409, detail="Ticket already resolved")

    resolved_at = payload.get("resolved_at")
    if not resolved_at:
        raise HTTPException(status_code=400, detail="resolved_at is required")

    try:
        resolved_dt = datetime.fromisoformat(resolved_at)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid resolved_at format"
        )

    ticket.resolved_at = resolved_dt
    ticket.resolved_by = current_user.id
    ticket.updated_at = datetime.utcnow()

    # Auto-tag the ticket using AI
    # Fetch conversation messages for classification
    ticket_message = ticket.message
    msgs_query = db.query(Message).filter(
        Message.customer_id == ticket.customer_id
    )
    if ticket_message and ticket_message.created_at:
        msgs_query = msgs_query.filter(
            Message.created_at >= ticket_message.created_at,
        )
    msgs = msgs_query.order_by(Message.created_at.asc()).limit(50).all()

    # Build message list for tagging
    messages_for_tagging = [
        {
            "body": m.body,
            "from_source": get_from_source_string(m.from_source),
        }
        for m in msgs
    ]

    # Classify the ticket
    tagging_result = await classify_ticket(messages_for_tagging)
    if tagging_result:
        ticket.tag = tagging_result.tag.value
        ticket.tag_confidence = tagging_result.confidence

    db.commit()
    db.refresh(ticket)

    # Emit WebSocket event for ticket resolution
    asyncio.create_task(
        emit_ticket_resolved(
            ticket_id=ticket.id,
            resolved_at=resolved_dt.isoformat(),
            resolved_by=current_user.full_name,
            administrative_id=ticket.administrative_id,
        )
    )

    return {"ticket": _serialize_ticket(ticket)}
