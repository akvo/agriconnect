import logging
import socketio
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserType
from models.administrative import UserAdministrative
from models.message import MessageFrom
from services.push_notification_service import PushNotificationService
from services.user_service import UserService
from utils.auth import verify_token

logger = logging.getLogger(__name__)

sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=False,
    ping_timeout=120,
    ping_interval=30,
    transports=["websocket", "polling"],
)

SOCKETIO_PATH = ""

sio_app = socketio.ASGIApp(
    sio_server,
    socketio_path=SOCKETIO_PATH,
)

USER_CACHE: Dict[int, str] = {}
CONNECTIONS: Dict[str, dict] = {}  # sid -> connection info
RATE_LIMITS: Dict[str, dict] = {}
RATE_LIMIT_WINDOW = timedelta(seconds=60)
MAX_JOINS_PER_WINDOW = 50
MAX_LEAVES_PER_WINDOW = 50


# Helper functions (same as before)
def set_user_cache(user_id: int, sid: str):
    USER_CACHE[user_id] = sid
    logger.info(f"[CACHE] Set: user {user_id} -> sid {sid}")


def get_user_cache(user_id: int) -> Optional[str]:
    sid = USER_CACHE.get(user_id)
    if sid:
        logger.debug(f"[CACHE] Get: user {user_id} -> sid {sid}")
    return sid


def delete_user_cache(user_id: int):
    if user_id in USER_CACHE:
        sid = USER_CACHE.pop(user_id)
        logger.info(f"[CACHE] Delete: user {user_id} (was sid {sid})")


def get_user_wards(user: User, db: Session) -> list[int]:
    if user.user_type == UserType.ADMIN:
        return []
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )
    return [ua.administrative_id for ua in user_admins]


def check_rate_limit(sid: str, action: str) -> bool:
    now = datetime.now(timezone.utc)
    if sid not in RATE_LIMITS:
        RATE_LIMITS[sid] = {
            "join_count": 0,
            "leave_count": 0,
            "window_start": now,
        }
    limits = RATE_LIMITS[sid]
    if now - limits["window_start"] > RATE_LIMIT_WINDOW:
        limits["join_count"] = 0
        limits["leave_count"] = 0
        limits["window_start"] = now
    if action == "join" and limits["join_count"] >= MAX_JOINS_PER_WINDOW:
        return False
    if action == "leave" and limits["leave_count"] >= MAX_LEAVES_PER_WINDOW:
        return False
    if action == "join":
        limits["join_count"] += 1
    elif action == "leave":
        limits["leave_count"] += 1
    return True


@sio_server.event
async def connect(
    sid: str, environ: dict, auth: Optional[dict] = None
):
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
                await sio_server.enter_room(sid, "ward:admin")
                logger.info(
                    f"[CONNECT] Admin user {user.id} joined ward:admin"
                )
            else:
                for ward_id in ward_ids:
                    room_name = f"ward:{ward_id}"
                    await sio_server.enter_room(sid, room_name)
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


@sio_server.event
async def disconnect(sid: str):
    """
    Handle disconnection with cleanup
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


@sio_server.event
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
        await sio_server.enter_room(sid, room_name)

        CONNECTIONS[sid]["last_activity"] = datetime.now(timezone.utc)

        logger.info(
            f"[JOIN_PLAYGROUND] Admin {user_info['user_id']} "
            f"joined {room_name}"
        )
        return {"success": True, "session_id": session_id}

    except Exception as e:
        logger.error(f"[JOIN_PLAYGROUND] Error: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}


async def emit_message_received(
    ticket_id: int,
    message_id: int,
    phone_number: str,
    body: str,
    from_source: int,
    ts: str,  # timestamp as ISO string
    administrative_id: Optional[int] = None,
    ticket_number: str = None,
    customer_name: str = None,
    sender_user_id: Optional[int] = None,
    customer_id: Optional[int] = None,
):
    """Emit message with ticket metadata for optimistic UI display"""
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "phone_number": phone_number,
        "body": body,
        "from_source": from_source,
        "ts": ts,
        "ticket_number": ticket_number,
        "customer_name": customer_name,
        "customer_id": customer_id,
    }

    # Emit to ward room
    if administrative_id:
        await sio_server.emit(
            "message_received",
            event_data,
            room=f"ward:{administrative_id}",
        )
        logger.info(
            f"[EMIT:TICKETS] message_received to ward:{administrative_id}"
        )

    # Emit to admin room
    await sio_server.emit(
        "message_received",
        event_data,
        room="ward:admin",
    )
    logger.info("[EMIT:TICKETS] message_received to ward:admin")

    # Push notifications
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
    finally:
        db.close()


async def emit_playground_response(
    session_id: str, message_id: int, content: str, response_time_ms: int
):
    """Emit response"""
    event_data = {
        "session_id": session_id,
        "message_id": message_id,
        "content": content,
        "response_time_ms": response_time_ms,
        "role": "assistant",
        "status": "completed",
    }

    room_name = f"playground:{session_id}"
    await sio_server.emit(
        "playground_response",
        event_data,
        room=room_name,
    )
    logger.info(
        f"[EMIT:PLAYGROUND] response for session {session_id}"
    )


async def emit_whisper_created(
    ticket_id: int,
    message_id: int,
    suggestion: str,
    customer_id: int,
    message_sid: str,
    created_at: str,
    administrative_id: Optional[int] = None,
):
    """Emit whisper"""
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "suggestion": suggestion,
        "customer_id": customer_id,
        "message_sid": message_sid,
        "from_source": MessageFrom.LLM,
        "message_type": "WHISPER",
        "ts": created_at,
    }

    await sio_server.emit(
        "whisper",  # Simpler name
        event_data,
        room="ward:admin",
    )
    if administrative_id:
        await sio_server.emit(
            "whisper",
            event_data,
            room=f"ward:{administrative_id}",
        )
    logger.info(f"[EMIT:TICKETS] whisper for ticket {ticket_id}")


async def emit_ticket_resolved(
    ticket_id: int, resolved_at: str, administrative_id: Optional[int] = None
):
    """Emit ticket resolved"""
    event_data = {
        "ticket_id": ticket_id,
        "resolved_at": resolved_at,
    }

    if administrative_id:
        await sio_server.emit(
            "ticket_resolved",
            event_data,
            room=f"ward:{administrative_id}",
        )
    await sio_server.emit(
        "ticket_resolved",
        event_data,
        room="ward:admin",
    )
    logger.info(f"[EMIT:TICKETS] ticket_resolved for {ticket_id}")


# Export
__all__ = [
    "sio_server",
    "sio_app",
    "emit_playground_response",
    "emit_message_received",
    "emit_ticket_resolved",
    "emit_whisper_created",
]
