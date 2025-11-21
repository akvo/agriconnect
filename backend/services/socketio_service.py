import logging
import socketio
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserType
from models.administrative import UserAdministrative
from services.push_notification_service import PushNotificationService
from services.user_service import UserService
from utils.auth import verify_token

logger = logging.getLogger(__name__)

# Configure Socket.IO server with mobile-optimized settings
sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,  # Enable for debugging WebSocket issues
    ping_timeout=120,  # Mobile stability (wait 120s for pong)
    ping_interval=130,  # Mobile battery life (send ping every 130s)
)

# Path relative to the mount point (/ws)
# Frontend connects to: /ws/socket.io/
# FastAPI mounts at /ws and strips it, so ASGI app sees: /socket.io/
#
# For socketio.ASGIApp:
# - Use empty string "" to handle all paths under the mount point
# - The default Socket.IO path "/socket.io/" will be handled automatically
SOCKETIO_PATH = ""

sio_app = socketio.ASGIApp(
    sio_server,
    socketio_path=SOCKETIO_PATH,
)

USER_CONNECTIONS: Dict[int, set] = {}  # user_id -> set of sids (multi-device)
CONNECTIONS: Dict[str, dict] = {}  # sid -> connection info
RATE_LIMITS: Dict[str, dict] = {}
RATE_LIMIT_WINDOW = timedelta(seconds=60)
MAX_JOINS_PER_WINDOW = 50
MAX_LEAVES_PER_WINDOW = 50


# Helper functions for multi-device connection tracking
def add_user_connection(user_id: int, sid: str):
    """Add socket connection for user (supports multiple devices)"""
    if user_id not in USER_CONNECTIONS:
        USER_CONNECTIONS[user_id] = set()
    USER_CONNECTIONS[user_id].add(sid)
    logger.info(
        f"[CONNECTIONS] Added: user {user_id} -> sid {sid} "
        f"(total sessions: {len(USER_CONNECTIONS[user_id])})"
    )


def get_user_connections(user_id: int) -> set:
    """Get all socket connections for a user"""
    return USER_CONNECTIONS.get(user_id, set())


def remove_user_connection(user_id: int, sid: str):
    """Remove socket connection for user"""
    if user_id in USER_CONNECTIONS:
        USER_CONNECTIONS[user_id].discard(sid)
        if not USER_CONNECTIONS[user_id]:
            del USER_CONNECTIONS[user_id]
            logger.info(
                f"[CONNECTIONS] User {user_id} has no more connections"
            )
        else:
            logger.info(
                f"[CONNECTIONS] Removed: user {user_id} -> sid {sid} "
                f"(remaining: {len(USER_CONNECTIONS[user_id])})"
            )


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


async def log_connected_clients():
    """Log all currently connected clients"""
    try:
        # List of all SIDs in the default namespace "/"
        has_manager = hasattr(sio_server, 'manager')
        has_rooms = has_manager and hasattr(sio_server.manager, 'rooms')
        if has_rooms:
            namespace_rooms = sio_server.manager.rooms.get('/', {})
            sids = list(namespace_rooms.keys())
            logging.info(f"Connected clients: {sids}")
    except Exception as e:
        logging.debug(f"Could not log connected clients: {e}")


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
                "connected_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
            }

            # Track multi-device connections
            add_user_connection(user.id, sid)

            # Join user-specific room (ONLY room needed - simplified!)
            user_room = f"user:{user.id}"
            await sio_server.enter_room(sid, user_room)
            logger.info(f"[CONNECT] User {user.id} joined {user_room}")

            logger.info(
                f"[CONNECT] ✅ Success: sid={sid}, user={user.id}, "
                f"type={user.user_type.value}, "
                f"sessions={len(USER_CONNECTIONS[user.id])}"
            )
            # Log current connections
            await log_connected_clients()
            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"[CONNECT] ❌ Error: {e}", exc_info=True)
        return False


@sio_server.event
async def disconnect(sid: str):
    """
    Handle disconnection with comprehensive cleanup
    """
    logger.info(f"[DISCONNECT] Client: {sid}")

    # Clean connection
    if sid in CONNECTIONS:
        user_info = CONNECTIONS.pop(sid)
        user_id = user_info.get("user_id")
        duration = datetime.now(timezone.utc) - user_info['connected_at']
        logger.info(f"[DISCONNECT] User {user_id}, duration: {duration}")

        # Remove from multi-device tracking
        if user_id:
            remove_user_connection(user_id, sid)

    # Clean rate limits
    if sid in RATE_LIMITS:
        RATE_LIMITS.pop(sid)
    # Log current connections
    await log_connected_clients()


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
    sender_name: str = None,
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
        "sender_name": sender_name,
    }

    # Conditional field based on sender type
    if sender_user_id:
        event_data["user_id"] = sender_user_id
    else:
        event_data["customer_id"] = customer_id

    # Determine which users should receive this message
    target_users = set()

    for sid, conn in CONNECTIONS.items():
        user_id = conn.get("user_id")
        user_type = conn.get("user_type")
        ward_ids = conn.get("ward_ids", [])

        # All ADMIN users receive all messages
        if user_type == UserType.ADMIN.value:
            target_users.add(user_id)
        # EO users only receive messages from their assigned wards
        elif administrative_id and administrative_id in ward_ids:
            target_users.add(user_id)

    # Broadcast to each user's room
    for user_id in target_users:
        await sio_server.emit(
            "message_received", event_data, room=f"user:{user_id}"
        )

    logger.info(
        f"[EMIT:TICKETS] message_received broadcast to "
        f"{len(target_users)} users "
        f"(ward_id: {administrative_id})"
    )

    # Push notifications
    db = next(get_db())
    try:
        push_service = PushNotificationService(db)
        push_service.notify_new_message(
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            customer_name=sender_name,
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
    try:
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
    except Exception as e:
        logger.error(
            f"[EMIT:PLAYGROUND] Error emitting response: {e}",
            exc_info=True
        )


async def emit_whisper_created(
    ticket_id: int,
    message_id: int,
    suggestion: str,
    customer_id: int,
    created_at: str,
    administrative_id: Optional[int] = None,
):
    """Emit whisper using user-specific rooms only"""
    event_data = {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "suggestion": suggestion,
        "customer_id": customer_id,
        "ts": created_at,
    }

    # Determine which users should receive this whisper
    target_users = set()

    for sid, conn in CONNECTIONS.items():
        user_id = conn.get("user_id")
        user_type = conn.get("user_type")
        ward_ids = conn.get("ward_ids", [])

        # All ADMIN users receive all whispers
        if user_type == UserType.ADMIN.value:
            target_users.add(user_id)
        # EO users only receive whispers from their assigned wards
        elif administrative_id and administrative_id in ward_ids:
            target_users.add(user_id)

    # Broadcast to each user's room
    for user_id in target_users:
        await sio_server.emit("whisper", event_data, room=f"user:{user_id}")

    logger.info(
        f"[EMIT:TICKETS] whisper for ticket {ticket_id} - "
        f"broadcast to {len(target_users)} users "
        f"(ward_id: {administrative_id})"
    )


async def emit_ticket_resolved(
    ticket_id: int,
    resolved_at: str,
    resolved_by: Optional[str] = None,
    administrative_id: Optional[int] = None
):
    """Emit ticket resolved using user-specific rooms only"""
    event_data = {
        "ticket_id": ticket_id,
        "resolved_at": resolved_at,
        "resolved_by": resolved_by,
    }

    # Determine which users should receive this event
    target_users = set()

    for sid, conn in CONNECTIONS.items():
        user_id = conn.get("user_id")
        user_type = conn.get("user_type")
        ward_ids = conn.get("ward_ids", [])

        # All ADMIN users receive all ticket resolutions
        if user_type == UserType.ADMIN.value:
            target_users.add(user_id)
        # EO users only receive resolutions from their assigned wards
        elif administrative_id and administrative_id in ward_ids:
            target_users.add(user_id)

    # Broadcast to each user's room
    for user_id in target_users:
        await sio_server.emit(
            "ticket_resolved", event_data, room=f"user:{user_id}"
        )

    logger.info(
        f"[EMIT:TICKETS] ticket_resolved for {ticket_id} - "
        f"broadcast to {len(target_users)} users "
        f"(ward_id: {administrative_id})"
    )


# Export
__all__ = [
    "sio_server",
    "sio_app",
    "emit_playground_response",
    "emit_message_received",
    "emit_ticket_resolved",
    "emit_whisper_created",
]
