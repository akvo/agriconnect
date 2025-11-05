"""
WebSocket (Socket.IO) router - REFACTORED with rag-doll patterns

Improvements:
- User cache for fast lookups (rag-doll pattern)
- Better logging with [TAGS] (rag-doll pattern)
- Room verification before emit (websocket-issue-analysis.md)
- Improved rate limiting with detailed logs
- Keep AgriConnect's room architecture (ward + ticket rooms)
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

import socketio
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserType
from models.administrative import UserAdministrative
from services.push_notification_service import PushNotificationService
from utils.auth import verify_token

logger = logging.getLogger(__name__)

# Socket.IO server (rag-doll-inspired config, mobile-optimized)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=False,
    ping_timeout=120,  # 2 minutes (lenient for mobile)
    ping_interval=30,  # 30 seconds
    transports=["websocket", "polling"],  # Server supports both
)

sio_app = socketio.ASGIApp(
    sio,
    socketio_path="",  # Empty since mounted at /ws/socket.io
)

# Connection storage (rag-doll pattern: separate cache and connections)
USER_CACHE: Dict[int, str] = {}  # user_id -> sid (for fast lookups)
CONNECTIONS: Dict[str, dict] = {}  # sid -> connection info

# Rate limiting
RATE_LIMITS: Dict[str, dict] = {}
RATE_LIMIT_WINDOW = timedelta(seconds=60)
MAX_JOINS_PER_WINDOW = 50  # Increased from 30
MAX_LEAVES_PER_WINDOW = 50


def set_user_cache(user_id: int, sid: str):
    """Cache user's SID (rag-doll pattern)"""
    USER_CACHE[user_id] = sid
    logger.info(f"[CACHE] Set: user {user_id} -> sid {sid}")


def get_user_cache(user_id: int) -> Optional[str]:
    """Get cached SID for user"""
    sid = USER_CACHE.get(user_id)
    if sid:
        logger.debug(f"[CACHE] Get: user {user_id} -> sid {sid}")
    return sid


def delete_user_cache(user_id: int):
    """Remove user from cache"""
    if user_id in USER_CACHE:
        sid = USER_CACHE.pop(user_id)
        logger.info(f"[CACHE] Delete: user {user_id} (was sid {sid})")


def get_user_wards(user: User, db: Session) -> list[int]:
    """Get list of ward IDs accessible by user"""
    if user.user_type == UserType.ADMIN:
        return []  # Empty = admin (all wards)

    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )
    return [ua.administrative_id for ua in user_admins]


def check_rate_limit(sid: str, action: str) -> bool:
    """
    Check rate limits with detailed logging (improved from analysis)
    """
    now = datetime.utcnow()

    if sid not in RATE_LIMITS:
        RATE_LIMITS[sid] = {
            "join_count": 0,
            "leave_count": 0,
            "window_start": now,
        }

    limits = RATE_LIMITS[sid]

    # Reset window if expired
    if now - limits["window_start"] > RATE_LIMIT_WINDOW:
        if limits["join_count"] > 0 or limits["leave_count"] > 0:
            logger.info(
                f"[RATE_LIMIT] Window reset for {sid}: "
                f"joins={limits['join_count']}, leaves={limits['leave_count']}"
            )
        limits["join_count"] = 0
        limits["leave_count"] = 0
        limits["window_start"] = now

    # Check and LOG violations (websocket-issue-analysis.md)
    if action == "join" and limits["join_count"] >= MAX_JOINS_PER_WINDOW:
        user_info = CONNECTIONS.get(sid, {})
        logger.warning(
            f"[RATE_LIMIT_EXCEEDED] Join limit for {sid} "
            f"(user {user_info.get('user_id')}): "
            f"{limits['join_count']}/{MAX_JOINS_PER_WINDOW}"
        )
        return False

    if action == "leave" and limits["leave_count"] >= MAX_LEAVES_PER_WINDOW:
        user_info = CONNECTIONS.get(sid, {})
        logger.warning(
            f"[RATE_LIMIT_EXCEEDED] Leave limit for {sid} "
            f"(user {user_info.get('user_id')}): "
            f"{limits['leave_count']}/{MAX_LEAVES_PER_WINDOW}"
        )
        return False

    # Increment
    if action == "join":
        limits["join_count"] += 1
    elif action == "leave":
        limits["leave_count"] += 1

    return True


@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    """
    Handle client connection (rag-doll-inspired, AgriConnect auth)
    """
    logger.info(f"[CONNECT] Client attempting: {sid}")

    try:
        # Extract token
        token = None
        if auth and "token" in auth:
            token = auth["token"]
            logger.debug("[CONNECT] Token from auth dict")
        elif "HTTP_AUTHORIZATION" in environ:
            auth_header = environ["HTTP_AUTHORIZATION"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                logger.debug("[CONNECT] Token from header")

        if not token:
            logger.warning(f"[CONNECT] No token: {sid}")
            return False

        # Verify token
        try:
            payload = verify_token(token)
            email = payload.get("sub")
            if not email:
                logger.warning(f"[CONNECT] Invalid payload: {sid}")
                return False
        except Exception as e:
            logger.warning(f"[CONNECT] Token verify failed: {e}")
            return False

        # Get user
        db: Session = next(get_db())
        try:
            from services.user_service import UserService

            user = UserService.get_user_by_email(db, email)
            if not user or not user.is_active:
                logger.warning(f"[CONNECT] User not found/inactive: {sid}")
                return False

            # Get wards
            ward_ids = get_user_wards(user, db)

            # Store connection (rag-doll pattern + AgriConnect data)
            CONNECTIONS[sid] = {
                "user_id": user.id,
                "user_type": user.user_type.value,
                "ward_ids": ward_ids,
                "connected_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
            }

            # Cache user SID (rag-doll pattern)
            set_user_cache(user.id, sid)

            # Join ward rooms
            if user.user_type == UserType.ADMIN:
                await sio.enter_room(sid, "ward:admin")
                logger.info(
                    f"[CONNECT] Admin user {user.id} joined ward:admin"
                )
            else:
                for ward_id in ward_ids:
                    room_name = f"ward:{ward_id}"
                    await sio.enter_room(sid, room_name)
                    logger.info(
                        f"[CONNECT] User {user.id} joined {room_name}"
                    )

            logger.info(
                f"[CONNECT] ✅ Success: {sid} "
                f"(user {user.id}, {user.user_type.value}, wards {ward_ids})"
            )
            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"[CONNECT] ❌ Error: {e}", exc_info=True)
        return False


@sio.event
async def disconnect(sid: str):
    """
    Handle disconnection (rag-doll pattern)
    """
    logger.info(f"[DISCONNECT] Client: {sid}")

    # Clean connection
    if sid in CONNECTIONS:
        user_info = CONNECTIONS.pop(sid)
        user_id = user_info.get("user_id")
        logger.info(f"[DISCONNECT] Cleaned user {user_id}")

        # Remove from cache
        if user_id:
            delete_user_cache(user_id)

    # Clean rate limits
    if sid in RATE_LIMITS:
        RATE_LIMITS.pop(sid)


@sio.event
async def join_ticket(sid: str, data: dict):
    """
    Join ticket room (needed for AgriConnect multi-user coordination)
    """
    if sid not in CONNECTIONS:
        logger.warning(f"[JOIN_TICKET] Unknown client: {sid}")
        return {"success": False, "error": "Not authenticated"}

    if not check_rate_limit(sid, "join"):
        return {"success": False, "error": "Rate limit exceeded"}

    ticket_id = data.get("ticket_id")
    if not ticket_id:
        return {"success": False, "error": "ticket_id required"}

    try:
        db: Session = next(get_db())
        try:
            from models.ticket import Ticket

            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            user_info = CONNECTIONS[sid]
            user_type = user_info.get("user_type")

            # Check access
            if user_type != UserType.ADMIN.value:
                ward_ids = user_info.get("ward_ids", [])
                if ticket.administrative_id not in ward_ids:
                    logger.warning(
                        f"[JOIN_TICKET] Access denied: "
                        f"user {user_info['user_id']} to ticket {ticket_id}"
                    )
                    return {"success": False, "error": "Access denied"}

            # Join room
            room_name = f"ticket:{ticket_id}"
            await sio.enter_room(sid, room_name)

            CONNECTIONS[sid]["last_activity"] = datetime.utcnow()

            logger.info(
                f"[JOIN_TICKET] ✅ User {user_info['user_id']} "
                f"joined {room_name}"
            )
            return {"success": True, "ticket_id": ticket_id}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"[JOIN_TICKET] ❌ Error: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}


@sio.event
async def leave_ticket(sid: str, data: dict):
    """Leave ticket room"""
    if sid not in CONNECTIONS:
        return {"success": False, "error": "Not authenticated"}

    if not check_rate_limit(sid, "leave"):
        return {"success": False, "error": "Rate limit exceeded"}

    ticket_id = data.get("ticket_id")
    if not ticket_id:
        return {"success": False, "error": "ticket_id required"}

    try:
        room_name = f"ticket:{ticket_id}"
        await sio.leave_room(sid, room_name)

        user_info = CONNECTIONS[sid]
        CONNECTIONS[sid]["last_activity"] = datetime.utcnow()

        logger.info(
            f"[LEAVE_TICKET] User {user_info['user_id']} left {room_name}"
        )
        return {"success": True, "ticket_id": ticket_id}

    except Exception as e:
        logger.error(f"[LEAVE_TICKET] Error: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}


@sio.event
async def join_playground(sid: str, data: dict):
    """Join playground session (admin only)"""
    if sid not in CONNECTIONS:
        return {"success": False, "error": "Not authenticated"}

    if not check_rate_limit(sid, "join"):
        return {"success": False, "error": "Rate limit exceeded"}

    user_info = CONNECTIONS[sid]
    if user_info.get("user_type") != UserType.ADMIN.value:
        return {"success": False, "error": "Admin access required"}

    session_id = data.get("session_id")
    if not session_id:
        return {"success": False, "error": "session_id required"}

    try:
        room_name = f"playground:{session_id}"
        await sio.enter_room(sid, room_name)

        CONNECTIONS[sid]["last_activity"] = datetime.utcnow()

        logger.info(
            f"[JOIN_PLAYGROUND] Admin {user_info['user_id']} "
            f"joined {room_name}"
        )
        return {"success": True, "session_id": session_id}

    except Exception as e:
        logger.error(f"[JOIN_PLAYGROUND] Error: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}


@sio.event
async def ping(sid: str, data: dict = None):
    """
    Connection verification ping (from websocket-issue-analysis.md)
    """
    if sid in CONNECTIONS:
        CONNECTIONS[sid]["last_activity"] = datetime.utcnow()
        logger.debug(f"[PING] {sid} -> pong")
        return "pong"
    else:
        logger.warning(f"[PING] Unknown client: {sid}")
        return None


# Emit helpers with room verification (websocket-issue-analysis.md)

async def emit_message_created(
    ticket_id: int,
    message_id: int,
    message_sid: str,
    customer_id: int,
    body: str,
    from_source: int,
    ts: str,
    administrative_id: Optional[int] = None,
    ticket_number: str = None,
    customer_name: str = None,
    sender_user_id: Optional[int] = None,
):
    """Emit message_created with room verification"""
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "message_sid": message_sid,
        "customer_id": customer_id,
        "body": body,
        "from_source": from_source,
        "ts": ts,
    }

    # Emit to ticket room WITH VERIFICATION
    room_name = f"ticket:{ticket_id}"
    try:
        participants = list(sio.manager.get_participants("/", room_name))

        if participants:
            logger.info(
                f"[EMIT] message_created to {len(participants)} "
                f"clients in {room_name}: {participants}"
            )
            await sio.emit("message_created", event_data, room=room_name)
        else:
            logger.warning(
                f"[EMIT_SKIP] No participants in {room_name} "
                f"for message {message_id}"
            )
    except Exception as e:
        logger.error(f"[EMIT_ERROR] {room_name}: {e}")

    # Emit to ward room
    if administrative_id:
        try:
            ward_room = f"ward:{administrative_id}"
            ward_participants = list(
                sio.manager.get_participants("/", ward_room)
            )
            logger.info(
                f"[EMIT] message_created to {ward_room} "
                f"({len(ward_participants)} participants)"
            )
            await sio.emit("message_created", event_data, room=ward_room)
        except Exception as e:
            logger.error(f"[EMIT_ERROR] ward room: {e}")

    # Emit to admin room
    try:
        await sio.emit("message_created", event_data, room="ward:admin")
    except Exception as e:
        logger.error(f"[EMIT_ERROR] admin room: {e}")

    logger.info(
        f"[EMIT] Completed message_created for message {message_id}"
    )

    # Push notifications (only if no active viewers)
    if all([administrative_id, ticket_number, customer_name]):
        try:
            participants = list(sio.manager.get_participants("/", room_name))

            if not participants:
                # No one viewing - send push
                db = next(get_db())
                try:
                    push_service = PushNotificationService(db)
                    push_service.notify_new_message(
                        ticket_id=ticket_id,
                        ticket_number=ticket_number,
                        customer_name=customer_name,
                        administrative_id=administrative_id,
                        message_id=message_id,
                        message_body=body,
                        sender_user_id=sender_user_id,
                    )
                    logger.info(
                        f"[PUSH] Sent for message {message_id} "
                        f"(ticket {ticket_number})"
                    )
                finally:
                    db.close()
            else:
                logger.info(
                    f"[PUSH] Skipped for message {message_id} - "
                    f"{len(participants)} users viewing"
                )
        except Exception as e:
            logger.error(f"[PUSH_ERROR]: {e}", exc_info=True)


async def emit_message_status_updated(
    ticket_id: int,
    message_id: int,
    status: str,
    updated_at: str,
    updated_by: Optional[int] = None,
    administrative_id: Optional[int] = None,
):
    """Emit message status update"""
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "status": status,
        "updated_at": updated_at,
        "updated_by": updated_by,
    }

    await sio.emit(
        "message_status_updated", event_data, room=f"ticket:{ticket_id}"
    )

    if administrative_id:
        await sio.emit(
            "message_status_updated",
            event_data,
            room=f"ward:{administrative_id}",
        )

    await sio.emit("message_status_updated", event_data, room="ward:admin")

    logger.info(
        f"[EMIT] message_status_updated for message {message_id} "
        f"in ticket {ticket_id}"
    )


async def emit_ticket_resolved(
    ticket_id: int, resolved_at: str, administrative_id: Optional[int] = None
):
    """Emit ticket resolved event"""
    event_data = {
        "ticket_id": ticket_id,
        "resolved_at": resolved_at,
    }

    await sio.emit("ticket_resolved", event_data, room=f"ticket:{ticket_id}")

    if administrative_id:
        await sio.emit(
            "ticket_resolved", event_data, room=f"ward:{administrative_id}"
        )

    await sio.emit("ticket_resolved", event_data, room="ward:admin")

    logger.info(f"[EMIT] ticket_resolved for ticket {ticket_id}")


async def emit_ticket_created(
    ticket_id: int,
    customer_id: int,
    administrative_id: int,
    created_at: str,
    ticket_number: str = None,
    customer_name: str = None,
    message_id: int = None,
    message_preview: str = None,
):
    """Emit ticket created with push notifications"""
    event_data = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "administrative_id": administrative_id,
        "created_at": created_at,
    }

    await sio.emit(
        "ticket_created", event_data, room=f"ward:{administrative_id}"
    )
    await sio.emit("ticket_created", event_data, room="ward:admin")

    logger.info(f"[EMIT] ticket_created for ticket {ticket_id}")

    # Push notifications
    if all([ticket_number, customer_name, message_id, message_preview]):
        try:
            db = next(get_db())
            try:
                push_service = PushNotificationService(db)
                push_service.notify_new_ticket(
                    ticket_id=ticket_id,
                    ticket_number=ticket_number,
                    customer_name=customer_name,
                    administrative_id=administrative_id,
                    message_id=message_id,
                    message_preview=message_preview,
                )
                logger.info(
                    f"[PUSH] Sent for new ticket {ticket_number}"
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[PUSH_ERROR]: {e}", exc_info=True)


async def emit_whisper_created(
    ticket_id: int,
    message_id: int,
    suggestion: str,
):
    """Emit whisper (AI suggestion) event"""
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "suggestion": suggestion,
    }

    await sio.emit("whisper_created", event_data, room=f"ticket:{ticket_id}")

    logger.info(
        f"[EMIT] whisper_created for message {message_id} "
        f"in ticket {ticket_id}"
    )


async def emit_playground_response(
    session_id: str, message_id: int, content: str, response_time_ms: int
):
    """Emit playground response"""
    event_data = {
        "session_id": session_id,
        "message_id": message_id,
        "content": content,
        "response_time_ms": response_time_ms,
        "role": "assistant",
        "status": "completed",
    }

    room_name = f"playground:{session_id}"
    await sio.emit("playground_response", event_data, room=room_name)

    logger.info(
        f"[EMIT] playground_response for session {session_id}, "
        f"message {message_id} (response_time: {response_time_ms}ms)"
    )


# Export
__all__ = [
    "sio",
    "sio_app",
    "emit_message_created",
    "emit_message_status_updated",
    "emit_ticket_resolved",
    "emit_ticket_created",
    "emit_whisper_created",
    "emit_playground_response",
]
