"""
WebSocket (Socket.IO) router for real-time chat and ticket updates.

Implements requirements from ws_requirements.md:
- Socket.IO endpoint /ws with WebSocket transport
- Bearer token authentication on connect
- Room-based event distribution (ward-based and ticket-based)
- Events: message_created, message_status_updated, ticket_resolved
- Automatic reconnection support with heartbeat/ping
- Rate limiting on client emits
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

import socketio
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserType
from models.administrative import UserAdministrative
from utils.auth import verify_token

logger = logging.getLogger(__name__)

# Create Socket.IO server with async mode
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # Configure appropriately for production
    logger=True,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
)

# Socket.IO ASGI app - standard mounting approach
# This will be mounted at /ws in main.py
sio_app = socketio.ASGIApp(
    sio,
    socketio_path="",  # Empty path since we mount at /ws/socket.io
)


# In-memory storage for connection metadata
# Format: {sid: {"user_id": int, "ward_ids": [int], "last_action": datetime}}
connections: Dict[str, dict] = {}

# Rate limiting storage
# Format: {sid: {"join_count": int, "leave_count": int,
#               "window_start": datetime}}
rate_limits: Dict[str, dict] = {}

# Rate limit configuration
RATE_LIMIT_WINDOW = timedelta(seconds=60)  # 1 minute window
MAX_JOINS_PER_WINDOW = 30
MAX_LEAVES_PER_WINDOW = 30


def get_user_ward_ids(user: User, db: Session) -> list[int]:
    """Get list of ward (administrative) IDs accessible by the user."""
    if user.user_type == UserType.ADMIN:
        # Admin can access all wards - return empty list as a marker
        return []

    # EO can only access their assigned wards
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )

    return [ua.administrative_id for ua in user_admins]


def check_rate_limit(sid: str, action: str) -> bool:
    """Check if the client has exceeded rate limits for join/leave actions."""
    now = datetime.utcnow()

    if sid not in rate_limits:
        rate_limits[sid] = {
            "join_count": 0,
            "leave_count": 0,
            "window_start": now,
        }

    limits = rate_limits[sid]

    # Reset window if expired
    if now - limits["window_start"] > RATE_LIMIT_WINDOW:
        limits["join_count"] = 0
        limits["leave_count"] = 0
        limits["window_start"] = now

    # Check limits
    if action == "join" and limits["join_count"] >= MAX_JOINS_PER_WINDOW:
        return False
    if action == "leave" and limits["leave_count"] >= MAX_LEAVES_PER_WINDOW:
        return False

    # Increment counter
    if action == "join":
        limits["join_count"] += 1
    elif action == "leave":
        limits["leave_count"] += 1

    return True


@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    """
    Handle client connection.
    Verify Bearer token and join user to their ward rooms.
    """
    logger.info(f"Client attempting to connect: {sid}")
    logger.info(f"Auth dict: {auth}")
    auth_header = environ.get('HTTP_AUTHORIZATION', 'NOT PRESENT')
    logger.info(f"HTTP_AUTHORIZATION header: {auth_header}")

    try:
        # Extract token from auth dict or Authorization header
        token = None
        if auth and "token" in auth:
            token = auth["token"]
            token_preview = f"{token[:20]}..." if token else "No token"
            logger.info(f"Token from auth dict: {token_preview}")
        elif "HTTP_AUTHORIZATION" in environ:
            auth_header = environ["HTTP_AUTHORIZATION"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                token_preview = f"{token[:20]}..." if token else "No token"
                logger.info(f"Token from header: {token_preview}")

        if not token:
            logger.warning(f"No token provided for connection: {sid}")
            logger.warning(f"Available environ keys: {list(environ.keys())}")
            return False

        # Verify token and get user
        try:
            payload = verify_token(token)
            email = payload.get("sub")
            if not email:
                logger.warning(f"Invalid token payload for connection: {sid}")
                return False
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return False

        # Get user from database
        db: Session = next(get_db())
        try:
            from services.user_service import UserService

            user = UserService.get_user_by_email(db, email)
            if not user or not user.is_active:
                logger.warning(
                    f"User not found or inactive for connection: {sid}"
                )
                return False

            # Get user's ward IDs
            ward_ids = get_user_ward_ids(user, db)

            # Store connection metadata
            connections[sid] = {
                "user_id": user.id,
                "ward_ids": ward_ids,
                "last_action": datetime.utcnow(),
                "user_type": user.user_type.value,
            }

            # Join ward rooms
            if user.user_type == UserType.ADMIN:
                # Admin joins a special "admin" room to receive all events
                await sio.enter_room(sid, "ward:admin")
                logger.info(f"Admin user {user.id} joined ward:admin room")
            else:
                for ward_id in ward_ids:
                    room_name = f"ward:{ward_id}"
                    await sio.enter_room(sid, room_name)
                    logger.info(
                        f"User {user.id} joined room {room_name} (sid: {sid})"
                    )

            logger.info(
                f"Client connected successfully: {sid}, "
                f"user_id: {user.id}, wards: {ward_ids}"
            )
            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during connection: {e}", exc_info=True)
        return False


@sio.event
async def disconnect(sid: str):
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {sid}")

    # Clean up connection metadata
    if sid in connections:
        user_info = connections.pop(sid)
        logger.info(
            f"Cleaned up connection data for user_id: "
            f"{user_info.get('user_id')}"
        )

    # Clean up rate limit data
    if sid in rate_limits:
        rate_limits.pop(sid)


@sio.event
async def join_ticket(sid: str, data: dict):
    """
    Handle client joining a specific ticket room.
    Emitted when user opens a ticket chat view.
    """
    if sid not in connections:
        logger.warning(f"Unknown client attempting to join ticket: {sid}")
        return {"success": False, "error": "Not authenticated"}

    # Rate limiting
    if not check_rate_limit(sid, "join"):
        logger.warning(f"Rate limit exceeded for join_ticket: {sid}")
        return {"success": False, "error": "Rate limit exceeded"}

    ticket_id = data.get("ticket_id")
    if not ticket_id:
        return {"success": False, "error": "ticket_id is required"}

    try:
        # Verify user has access to this ticket
        db: Session = next(get_db())
        try:
            from models.ticket import Ticket

            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            user_info = connections[sid]
            user_type = user_info.get("user_type")

            # Check access: admin has access to all, EO only to their wards
            if user_type != UserType.ADMIN.value:
                ward_ids = user_info.get("ward_ids", [])
                if ticket.administrative_id not in ward_ids:
                    logger.warning(
                        f"User {user_info['user_id']} denied access "
                        f"to ticket {ticket_id}"
                    )
                    return {"success": False, "error": "Access denied"}

            # Join ticket room
            room_name = f"ticket:{ticket_id}"
            await sio.enter_room(sid, room_name)

            connections[sid]["last_action"] = datetime.utcnow()
            logger.info(
                f"User {user_info['user_id']} joined ticket room "
                f"{room_name} (sid: {sid})"
            )

            return {"success": True, "ticket_id": ticket_id}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error joining ticket room: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}


@sio.event
async def leave_ticket(sid: str, data: dict):
    """
    Handle client leaving a specific ticket room.
    Emitted when user closes/leaves a ticket chat view.
    """
    if sid not in connections:
        logger.warning(f"Unknown client attempting to leave ticket: {sid}")
        return {"success": False, "error": "Not authenticated"}

    # Rate limiting
    if not check_rate_limit(sid, "leave"):
        logger.warning(f"Rate limit exceeded for leave_ticket: {sid}")
        return {"success": False, "error": "Rate limit exceeded"}

    ticket_id = data.get("ticket_id")
    if not ticket_id:
        return {"success": False, "error": "ticket_id is required"}

    try:
        room_name = f"ticket:{ticket_id}"
        await sio.leave_room(sid, room_name)

        user_info = connections[sid]
        connections[sid]["last_action"] = datetime.utcnow()

        logger.info(
            f"User {user_info['user_id']} left ticket room "
            f"{room_name} (sid: {sid})"
        )

        return {"success": True, "ticket_id": ticket_id}

    except Exception as e:
        logger.error(f"Error leaving ticket room: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}


# Helper functions for emitting events (called from REST endpoints)


async def emit_message_created(
    ticket_id: int,
    message_id: int,
    customer_id: int,
    body: str,
    kind: str,
    ts: str,
    ward_id: Optional[int] = None,
):
    """
    Emit message_created event to ticket room and ward room.
    Called when a new message is created via REST API.
    """
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "customer_id": customer_id,
        "body": body,
        "kind": kind,
        "ts": ts,
    }

    # Emit to ticket room (for users viewing the chat)
    await sio.emit("message_created", event_data, room=f"ticket:{ticket_id}")

    # Emit to ward room (for inbox updates)
    if ward_id:
        await sio.emit("message_created", event_data, room=f"ward:{ward_id}")

    # Emit to admin room
    await sio.emit("message_created", event_data, room="ward:admin")

    logger.info(
        f"Emitted message_created event for message {message_id} "
        f"in ticket {ticket_id}"
    )


async def emit_message_status_updated(
    ticket_id: int,
    message_id: int,
    status: str,
    updated_at: str,
    updated_by: Optional[int] = None,
    ward_id: Optional[int] = None,
):
    """
    Emit message_status_updated event to ticket room and ward room.
    Called when a message status is changed via REST API.
    """
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "status": status,
        "updated_at": updated_at,
        "updated_by": updated_by,
    }

    # Emit to ticket room (for users viewing the chat)
    await sio.emit(
        "message_status_updated", event_data, room=f"ticket:{ticket_id}"
    )

    # Emit to ward room (for inbox updates)
    if ward_id:
        await sio.emit(
            "message_status_updated", event_data, room=f"ward:{ward_id}"
        )

    # Emit to admin room
    await sio.emit("message_status_updated", event_data, room="ward:admin")

    logger.info(
        f"Emitted message_status_updated event for message {message_id} "
        f"in ticket {ticket_id}"
    )


async def emit_ticket_resolved(
    ticket_id: int, resolved_at: str, ward_id: Optional[int] = None
):
    """
    Emit ticket_resolved event to ticket room and ward room.
    Called when a ticket is marked as resolved via REST API.
    """
    event_data = {
        "ticket_id": ticket_id,
        "resolved_at": resolved_at,
    }

    # Emit to ticket room (for users viewing the chat)
    await sio.emit("ticket_resolved", event_data, room=f"ticket:{ticket_id}")

    # Emit to ward room (for inbox updates)
    if ward_id:
        await sio.emit("ticket_resolved", event_data, room=f"ward:{ward_id}")

    # Emit to admin room
    await sio.emit("ticket_resolved", event_data, room="ward:admin")

    logger.info(f"Emitted ticket_resolved event for ticket {ticket_id}")


# Export for use in other routers
__all__ = [
    "sio",
    "sio_app",
    "emit_message_created",
    "emit_message_status_updated",
    "emit_ticket_resolved",
]
