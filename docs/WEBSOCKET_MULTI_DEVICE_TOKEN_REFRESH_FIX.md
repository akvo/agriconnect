# Implementation Plan: WebSocket Multi-Device & Token Refresh Fix

**Date:** 2025-11-11
**Author:** AgriConnect Team
**Status:** Planning
**Objective:** Fix WebSocket reliability for multiple admin devices and implement proper token refresh for mobile app

---

## 📊 Overview

### Purpose

Fix two critical issues affecting real-time communication and authentication:
1. **Multi-device WebSocket reliability**: Ensure all admin devices receive real-time updates
2. **Mobile token refresh**: Enable automatic token refresh without requiring app restart

### Key Principles

1. **Multi-Device Support**: Support multiple devices per user without connection conflicts
2. **Broadcast Redundancy**: Use multiple room patterns to ensure message delivery
3. **Connection Health**: Monitor connection health with Socket.IO's built-in ping/pong
4. **Secure Token Management**: Store tokens in SecureStore with API client caching
5. **Automatic Reconnection**: WebSocket reconnects when token is refreshed

### User Experience

**Current (Broken)**:
```
Admin A on Device 1: Opens app → Receives all messages ✅
Admin B on Device 2: Opens app → Some messages missing ❌
Admin B: Waits 1 hour → Token expires → Cannot fetch data ❌
```

**After Fix**:
```
Admin A on Device 1: Opens app → Receives all messages ✅
Admin B on Device 2: Opens app → Receives all messages ✅
Admin B: Waits 1 hour → Token auto-refreshes → Continues working ✅
```

---

## 🎯 Problem Statement

### Issue 1: WebSocket Multi-Device Reliability

**Symptoms**:
- Multiple admin devices with different accounts don't all receive real-time updates reliably
- One device receives messages/tickets instantly while others experience delayed or missing updates
- Same user on multiple devices causes connection conflicts

**Current Implementation Issues**:
- Single socket-per-user caching (`USER_CACHE: Dict[int, str]`)
- No connection lifecycle logging
- No heartbeat mechanism for detecting stale connections
- Single broadcasting strategy without redundancy

### Issue 2: Token Refresh Not Working on Mobile

**Symptoms**:
- Mobile app cannot refresh access tokens when they expire
- Users forced to log out and log back in after 1 hour
- WebSocket doesn't reconnect when token is refreshed

**Current Implementation Issues**:
- Backend `/auth/refresh` endpoint expects httpOnly cookies (doesn't work for React Native)
- No token-based refresh endpoint for mobile
- Token stored in React state instead of secure storage
- No event-based token change detection

---

## 🔍 Root Cause Analysis

### WebSocket Issues

1. **Single-Device Caching**
   - `USER_CACHE: Dict[int, str]` maps user_id → single sid
   - When user connects from Device 2, Device 1's sid is overwritten
   - Device 1 loses connection tracking but appears "connected"

2. **No Connection Lifecycle Logging**
   - Cannot see which users joined which rooms
   - No visibility into room membership failures
   - Cannot verify if broadcasts reach intended recipients

3. **No Heartbeat Mechanism**
   - Stale connections appear "connected" on client
   - No automatic reconnection on connection degradation
   - Mobile app doesn't detect when WebSocket is silently broken

4. **Single Broadcasting Strategy**
   - Only broadcasts to `ward:admin` and `ward:{administrative_id}` rooms
   - No redundancy if ward-based broadcast fails
   - No user-specific targeting

### Token Refresh Issues

1. **Cookie-Based Refresh**
   ```python
   # backend/routers/auth.py:91-94
   @router.post("/refresh", response_model=dict)
   def refresh_token(
       refresh_token: str = Cookie(None),  # ❌ Expects cookie (browser-only)
       db: Session = Depends(get_db)
   ):
   ```
   React Native cannot use httpOnly cookies.

2. **No Refresh Token Storage**
   - Mobile app receives refresh_token but doesn't store it
   - No SecureStore integration for refresh tokens

3. **No Mobile Refresh Endpoint**
   - No endpoint that accepts refresh_token in request body
   - Mobile app has no way to refresh tokens

4. **Token in React State**
   ```typescript
   // Current: Token in user state (not ideal)
   interface UserState {
     accessToken: string;  // In memory only, lost on app restart
     refreshToken: string;
   }
   ```

---

## 📐 Architecture Design

### WebSocket Multi-Device Architecture

#### Design Decision: User-Specific Rooms Only

**Approach:** Use ONLY `user:{user_id}` rooms for ALL broadcasts (no ward rooms).

**Rationale:**
1. **Simplicity:** Single broadcasting pattern - all events go to `user:{user_id}` rooms
2. **No Duplicates:** Each user receives exactly one copy of each message
3. **Multi-Device Support:** Same user on multiple devices = multiple SIDs in same `user:{user_id}` room
4. **Easier Debugging:** Clear message path: event → `user:{user_id}` → all user's devices
5. **Future-Proof:** Per-user customization already structured if needed later

#### Hierarchical Access for Upper-Level Officers

**Added in Feature #124:** Extension Officers assigned to higher administrative levels (region/district) now receive events for all descendant wards.

**Implementation:**
- `get_user_wards()` function computes accessible ward IDs at connection time
- For ward-level EOs: Returns only their directly assigned ward(s)
- For region/district-level EOs: Returns all descendant ward IDs via `AdministrativeService.get_descendant_ward_ids()`
- Admin users receive all events regardless of ward assignment

**Example:**
```
EO assigned to "Kiharu District":
  - get_user_wards() returns [ward1_id, ward2_id, ward3_id, ...]
  - All wards under Kiharu District are included
  - EO receives WebSocket events for tickets in any of these wards
```

**Performance Analysis:**

| Metric | Ward Rooms (ward:admin) | User Rooms (user:{id}) | Impact |
|--------|------------------------|------------------------|--------|
| emit() calls | 1 call | N calls (N=admins) | +10-50 function calls |
| Network bandwidth | Same | Same | No difference |
| Socket sends | N sockets | N sockets | No difference |
| CPU overhead | ~1ms | ~2ms for 10 admins | Negligible |
| Memory | Slightly less | Slightly more | < 1KB difference |

**Infrastructure Considerations:**

- **AgriConnect Scale:**
  - Expected: 5-50 admin users
  - Expected: 10-100 concurrent connections
  - Verdict: Performance difference unmeasurable at this scale ✅

- **Socket.IO Capacity:**
  - Handles: 10,000+ concurrent connections per server
  - Broadcast: 1,000+ rooms in milliseconds
  - Verdict: No infrastructure limitation ✅

- **Alternative Considered (ward rooms + user rooms):**
  - Pros: Redundancy (if ward broadcast fails, user-specific works)
  - Cons: Duplicate messages, more complex, client must deduplicate
  - Decision: Rejected - adds complexity without meaningful benefit

**Final Decision:** User-specific rooms provide the best balance of simplicity, performance, and maintainability for AgriConnect's scale.

#### Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                     Multiple Devices & Users                    │
├────────────────────────────────────────────────────────────────┤
│  Device 1          Device 2          Device 3       Device 4   │
│  (Admin A)         (Admin B)         (Admin A)      (EO C)     │
│  sid_abc123        sid_xyz789        sid_def456     sid_ghi789 │
└────────┬──────────────────┬──────────────────┬─────────┬───────┘
         │                  │                  │         │
         ▼                  ▼                  ▼         ▼
┌────────────────────────────────────────────────────────────────┐
│                  Socket.IO Server (Backend)                     │
│                                                                 │
│  USER_CONNECTIONS: {                                           │
│    1: {sid_abc123, sid_def456},  // Admin A on 2 devices      │
│    2: {sid_xyz789},               // Admin B on 1 device       │
│    3: {sid_ghi789}                // EO C on 1 device          │
│  }                                                              │
│                                                                 │
│  ROOMS (User-Specific Only):                                   │
│    user:1 → [sid_abc123, sid_def456]  // All Admin A devices  │
│    user:2 → [sid_xyz789]               // All Admin B devices  │
│    user:3 → [sid_ghi789]               // All EO C devices     │
└────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────┐
│               Simplified Broadcast Strategy                     │
│                                                                 │
│  Customer sends message from Ward 5:                           │
│    1. Query: Which users should receive this?                  │
│       - All ADMIN users (user_type = ADMIN)                    │
│       - EO users with Ward 5 in their ward_ids                 │
│         (includes EOs assigned to parent region/district)      │
│    2. Broadcast:                                               │
│       emit("message_received", data, room="user:1")  // Admin A│
│       emit("message_received", data, room="user:2")  // Admin B│
│       emit("message_received", data, room="user:3")  // EO C   │
│                                                                 │
│  Result: All relevant users receive exactly ONE message        │
│          All devices of each user receive the message          │
└────────────────────────────────────────────────────────────────┘
```

### Token Management Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Mobile App (React Native)                  │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐         ┌──────────────────┐            │
│  │  SecureStore    │         │   API Client     │            │
│  │  (Encrypted)    │         │   (Cache)        │            │
│  │                 │         │                  │            │
│  │  accessToken  ──┼────────▶│  cachedToken    │            │
│  │  refreshToken   │         │                  │            │
│  └─────────────────┘         └────────┬─────────┘            │
│                                        │                       │
│                                        │ Emits TOKEN_CHANGED   │
│                                        ▼                       │
│  ┌─────────────────────────────────────────────────┐         │
│  │           useToken Hook (Reactive)              │         │
│  │  - Listens for TOKEN_CHANGED events             │         │
│  │  - Updates local state                           │         │
│  │  - Triggers WebSocket reconnection               │         │
│  └─────────────────────────────────────────────────┘         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                              │
│                                                                 │
│  POST /auth/login                                              │
│    → Returns: { access_token, refresh_token }                 │
│                                                                 │
│  POST /auth/refresh-mobile  (NEW)                             │
│    ← Body: { refresh_token }                                  │
│    → Returns: { access_token }                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Solution Overview

### Approach: User-Specific Room Broadcasting + Socket.IO Ping/Pong + Token Caching

**WebSocket Improvements**:
1. **Multi-device tracking**: `USER_CONNECTIONS: Dict[int, Set[str]]` supports multiple SIDs per user
2. **User-specific rooms ONLY**: Use `user:{user_id}` rooms for ALL broadcasts (no ward rooms)
3. **Simplified broadcasting**: Single broadcast pattern - emit to each relevant user's room
4. **Socket.IO ping/pong**: Built-in connection health monitoring (ping every 30s, timeout 120s)
5. **Comprehensive logging**: Track all connection/disconnection events and room memberships

**Why User-Specific Rooms Only?**
- Simpler code (one broadcasting pattern)
- No duplicate messages (each user gets exactly one copy)
- Multi-device support maintained (same user_id, multiple devices in same room)
- Negligible performance difference at AgriConnect's scale (< 100 concurrent users)
- Easier to debug and maintain

**Token Management Improvements**:
1. **Mobile refresh endpoint**: `/auth/refresh-mobile` accepts refresh_token in request body
2. **SecureStore integration**: Store both tokens in encrypted storage (expo-secure-store)
3. **API client caching**: Token cached in memory with event-based change notification
4. **Automatic reconnection**: WebSocket reconnects when token changes (via useToken hook)

## Implementation Plan

### Phase 1: Backend - Mobile Token Refresh Endpoint

**File**: `backend/routers/auth.py`

#### 1.1 Add Request Schema

```python
from pydantic import BaseModel

class RefreshTokenRequest(BaseModel):
    refresh_token: str
```

#### 1.2 Add `/auth/refresh-mobile` Endpoint

```python
@router.post("/refresh-mobile", response_model=dict)
def refresh_token_mobile(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token from request body (for mobile apps)"""
    if not request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    # Verify refresh token (reuse existing verify_refresh_token)
    payload = verify_refresh_token(request.refresh_token)
    email = payload.get("sub")
    user_type = payload.get("user_type")

    # Get user from database
    user = UserService.get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email, "user_type": user_type},
        expires_delta=access_token_expires,
    )

    logger.info(f"[AUTH] Mobile token refresh successful for user: {email}")

    return {"access_token": access_token, "token_type": "bearer"}
```

#### 1.3 Update TokenResponse Schema

**File**: `backend/schemas/user.py`

```python
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None  # ADD - optional for backward compatibility
    token_type: str = "bearer"
    user: UserResponse
```

#### 1.4 Update Login Endpoint

**File**: `backend/routers/auth.py`

```python
@router.post("/login", response_model=TokenResponse)
def login_user(...):
    # ... existing code to create tokens ...

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,  # ADD THIS LINE
        user=user_response
    )
```

---

### Phase 2: Backend - Enhanced WebSocket with Multi-Device Support

**File**: `backend/services/socketio_service.py`

#### 2.1 Replace Single-Device Cache

Replace `USER_CACHE` with `USER_CONNECTIONS`:

```python
# REPLACE (around line 33):
USER_CACHE: Dict[int, str] = {}

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

# WITH:
USER_CONNECTIONS: Dict[int, set] = {}  # user_id -> set of sids (multi-device)

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
            logger.info(f"[CONNECTIONS] User {user_id} has no more connections")
        else:
            logger.info(
                f"[CONNECTIONS] Removed: user {user_id} -> sid {sid} "
                f"(remaining: {len(USER_CONNECTIONS[user_id])})"
            )
```

#### 2.2 Update `connect()` Handler

Add user-specific room join and enhanced logging:

```python
@sio_server.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    """Handle client connection with enhanced logging"""
    logger.info(f"[CONNECT] Client attempting: {sid}")

    try:
        # ... existing token verification code ...

        # Store connection info with heartbeat timestamp
        CONNECTIONS[sid] = {
            "user_id": user.id,
            "user_type": user.user_type.value,
            "ward_ids": ward_ids,
            "connected_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
            "last_heartbeat": datetime.now(timezone.utc),  # ADD
        }

        # Track multi-device connections
        add_user_connection(user.id, sid)

        # Join user-specific room (ONLY room needed - simplified!)
        user_room = f"user:{user.id}"
        await sio_server.enter_room(sid, user_room)
        logger.info(f"[CONNECT] User {user.id} joined {user_room}")

        logger.info(
            f"[CONNECT] ✅ Success: sid={sid}, user={user.id}, "
            f"type={user.user_type.value}, sessions={len(USER_CONNECTIONS[user.id])}"
        )
        return True

    except Exception as e:
        logger.error(f"[CONNECT] ❌ Error: {e}", exc_info=True)
        return False
```

#### 2.3 Update `disconnect()` Handler

```python
@sio_server.event
async def disconnect(sid: str):
    """Handle disconnection with comprehensive cleanup"""
    logger.info(f"[DISCONNECT] Client: {sid}")

    if sid in CONNECTIONS:
        user_info = CONNECTIONS.pop(sid)
        user_id = user_info.get("user_id")
        duration = datetime.now(timezone.utc) - user_info['connected_at']
        logger.info(f"[DISCONNECT] User {user_id}, duration: {duration}")

        # Remove from multi-device tracking
        if user_id:
            remove_user_connection(user_id, sid)  # REPLACE delete_user_cache

    if sid in RATE_LIMITS:
        RATE_LIMITS.pop(sid)
```

#### 2.4 Verify Socket.IO Ping/Pong Configuration (Already Configured!)

Socket.IO ping/pong is **already configured** in the backend! ✅

**File**: `backend/services/socketio_service.py` (lines 16-24)

```python
sio_server = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=False,
    ping_timeout=120,    # ✅ Already set: 120 seconds
    ping_interval=30,    # ✅ Already set: 30 seconds
    transports=["websocket", "polling"],
)
```

**Current Configuration:**
- Server sends ping every **30 seconds**
- Server waits **120 seconds** for pong response
- If no pong received → client disconnected → auto-reconnects

**Optional Adjustment** (if needed for faster detection):
```python
ping_interval=25,  # Change from 30 to 25 seconds
ping_timeout=60,   # Change from 120 to 60 seconds
```

**No custom handler needed** - Socket.IO manages ping/pong automatically!

#### 2.5 Update `emit_message_received()` with User-Specific Room Broadcasting

Simplified broadcasting using ONLY user-specific rooms:

```python
async def emit_message_received(
    ticket_id: int,
    message_id: int,
    phone_number: str,
    body: str,
    from_source: int,
    ts: str,
    administrative_id: Optional[int] = None,
    ticket_number: str = None,
    sender_name: str = None,
    sender_user_id: Optional[int] = None,
    customer_id: Optional[int] = None,
):
    """Emit message using user-specific rooms only (simplified!)"""
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
        # EO users receive messages from their assigned wards (includes descendants)
        elif administrative_id and administrative_id in ward_ids:
            target_users.add(user_id)

    # Broadcast to each user's room
    for user_id in target_users:
        await sio_server.emit("message_received", event_data, room=f"user:{user_id}")

    logger.info(
        f"[EMIT:TICKETS] message_received broadcast to {len(target_users)} users "
        f"(ward_id: {administrative_id})"
    )

    # Push notifications (existing)
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
```

#### 2.6 Update `emit_whisper_created()` with User-Specific Room Broadcasting

Same pattern as emit_message_received - ONLY use user-specific rooms:

```python
async def emit_whisper_created(
    ticket_id: int,
    message_id: int,
    suggestion: str,
    customer_id: int,
    created_at: str,
    administrative_id: Optional[int] = None,
):
    """Emit whisper using user-specific rooms only (simplified!)"""
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
        # EO users receive whispers from their assigned wards (includes descendants)
        elif administrative_id and administrative_id in ward_ids:
            target_users.add(user_id)

    # Broadcast to each user's room
    for user_id in target_users:
        await sio_server.emit("whisper", event_data, room=f"user:{user_id}")

    logger.info(
        f"[EMIT:TICKETS] whisper for ticket {ticket_id} - "
        f"broadcast to {len(target_users)} users (ward_id: {administrative_id})"
    )
```

#### 2.7 Update `emit_ticket_resolved()` with User-Specific Room Broadcasting

Same pattern - ONLY use user-specific rooms:

```python
async def emit_ticket_resolved(
    ticket_id: int,
    resolved_at: str,
    resolved_by: Optional[str] = None,
    administrative_id: Optional[int] = None
):
    """Emit ticket resolved using user-specific rooms only (simplified!)"""
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
        # EO users receive resolutions from their assigned wards (includes descendants)
        elif administrative_id and administrative_id in ward_ids:
            target_users.add(user_id)

    # Broadcast to each user's room
    for user_id in target_users:
        await sio_server.emit("ticket_resolved", event_data, room=f"user:{user_id}")

    logger.info(
        f"[EMIT:TICKETS] ticket_resolved for {ticket_id} - "
        f"broadcast to {len(target_users)} users (ward_id: {administrative_id})"
    )
```

**Note**: No changes needed for `emit_playground_response()` - it already targets specific session room.

---

### Phase 3: Mobile - Token Management Infrastructure

#### 3.1 Create Token Event Emitter

**File**: `app/utils/tokenEvents.ts` (NEW)

```typescript
import { EventEmitter } from 'events';

export const tokenEmitter = new EventEmitter();
export const TOKEN_CHANGED = 'token_changed';
```

#### 3.2 Create useToken Hook

**File**: `app/hooks/useToken.ts` (NEW)

```typescript
import { useState, useEffect } from 'react';
import { tokenEmitter, TOKEN_CHANGED } from '@/utils/tokenEvents';
import * as SecureStore from 'expo-secure-store';

export const useToken = () => {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load initial token from SecureStore
    (async () => {
      try {
        const storedToken = await SecureStore.getItemAsync('accessToken');
        setToken(storedToken);
        console.log('[useToken] Loaded token from SecureStore');
      } catch (error) {
        console.error('[useToken] Failed to load token:', error);
      } finally {
        setLoading(false);
      }
    })();

    // Listen for token changes from API client
    const handleTokenChange = (newToken: string | null) => {
      console.log('[useToken] Token changed:', newToken ? 'new token' : 'cleared');
      setToken(newToken);
    };

    tokenEmitter.on(TOKEN_CHANGED, handleTokenChange);

    return () => {
      tokenEmitter.off(TOKEN_CHANGED, handleTokenChange);
    };
  }, []);

  return { token, loading };
};
```

#### 3.3 Update API Client with Token Caching

**File**: `app/services/api.ts`

Key changes:
1. Add token caching with event emission
2. Auto-inject token from cache/SecureStore
3. Remove token parameter from ALL methods
4. Add `refreshTokenMobile()` method

```typescript
import * as SecureStore from 'expo-secure-store';
import { tokenEmitter, TOKEN_CHANGED } from '@/utils/tokenEvents';

class ApiClient {
  private baseUrl: string;
  private cachedToken: string | null = null;
  // ... existing handlers ...

  // NEW: Set token and emit event
  setAccessToken(token: string) {
    const tokenChanged = this.cachedToken !== token;
    this.cachedToken = token;

    if (tokenChanged) {
      console.log('[API] Token updated in cache');
      tokenEmitter.emit(TOKEN_CHANGED, token);
    }
  }

  // NEW: Clear token and emit event
  clearToken() {
    console.log('[API] Token cleared from cache');
    this.cachedToken = null;
    tokenEmitter.emit(TOKEN_CHANGED, null);
  }

  // NEW: Get token from cache or SecureStore
  private async getAccessToken(): Promise<string> {
    if (this.cachedToken) {
      return this.cachedToken;
    }

    const token = await SecureStore.getItemAsync('accessToken');
    if (!token) {
      throw new Error('No access token available');
    }

    this.cachedToken = token;
    return token;
  }

  // UPDATED: Use new token management
  private async refreshAccessToken(): Promise<string> {
    // ... existing refresh logic ...

    const newAccessToken = await this.refreshTokenHandler();
    this.setAccessToken(newAccessToken);  // Emit event

    return newAccessToken;
  }

  // UPDATED: Auto-inject token
  private async fetchWithRetry(url: string, options: RequestInit & { _retry?: boolean } = {}, isAuthEndpoint: boolean = false): Promise<Response> {
    let token: string | null = null;
    if (!isAuthEndpoint) {
      token = await this.getAccessToken();  // Auto-inject
    }

    const finalOptions = {
      ...options,
      headers: {
        ...options.headers,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    };

    const response = await fetch(url, finalOptions);

    // ... existing 401 handling with token refresh ...
  }

  // NEW: Mobile token refresh
  async refreshTokenMobile(refreshToken: string): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/auth/refresh-mobile`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      },
      true
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Token refresh failed" }));
      throw new Error(error.detail || "Token refresh failed");
    }

    return response.json();
  }

  // REMOVE token parameter from ALL methods:
  async getTickets(status: "open" | "resolved", page: number = 1, size?: number): Promise<any> {
    // Token auto-injected, no parameter needed!
  }

  async getMessages(ticketId: number, beforeTs?: string, limit: number = 20): Promise<any> {
    // Token auto-injected!
  }

  async sendMessage(ticketId: number, body: string, fromSource: number): Promise<any> {
    // Token auto-injected!
  }

  // ... apply same pattern to ALL other methods
}
```

---

### Phase 4: Mobile - Update AuthContext

**File**: `app/contexts/AuthContext.tsx`

Remove token from user state, use SecureStore + API client caching:

```typescript
import * as SecureStore from 'expo-secure-store';
import { api } from '@/services/api';

interface UserState {
  id: number;
  email: string;
  name: string;
  userType: string;
  // NO tokens!
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSession();
  }, []);

  const loadSession = async () => {
    try {
      const accessToken = await SecureStore.getItemAsync('accessToken');
      const refreshToken = await SecureStore.getItemAsync('refreshToken');
      const userDataJson = await SecureStore.getItemAsync('userData');

      if (!accessToken || !userDataJson) {
        setLoading(false);
        return;
      }

      const userData = JSON.parse(userDataJson);

      // Check token expiry, auto-refresh if needed
      try {
        const payload = JSON.parse(atob(accessToken.split('.')[1]));
        const exp = payload.exp * 1000;

        if (Date.now() >= exp && refreshToken) {
          console.log('[Auth] Token expired, auto-refreshing');
          const newToken = await refreshAccessToken();
          api.setAccessToken(newToken);
        } else {
          api.setAccessToken(accessToken);
        }
      } catch (e) {
        api.setAccessToken(accessToken);
      }

      setUser(userData);
      api.setRefreshTokenHandler(refreshAccessToken);
      api.setClearSessionHandler(clearSession);

      console.log('[Auth] Session restored');
    } catch (error) {
      console.error('[Auth] Failed to load session:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshAccessToken = async (): Promise<string> => {
    const refreshToken = await SecureStore.getItemAsync('refreshToken');
    if (!refreshToken) throw new Error('No refresh token');

    const response = await api.refreshTokenMobile(refreshToken);
    await SecureStore.setItemAsync('accessToken', response.access_token);

    return response.access_token;
  };

  const login = async (email: string, password: string) => {
    const response = await api.login({ email, password });

    // Store in SecureStore
    await SecureStore.setItemAsync('accessToken', response.access_token);
    await SecureStore.setItemAsync('refreshToken', response.refresh_token);
    await SecureStore.setItemAsync('userData', JSON.stringify({
      id: response.user.id,
      email: response.user.email,
      name: response.user.full_name,
      userType: response.user.user_type,
    }));

    // Cache in API client
    api.setAccessToken(response.access_token);

    // Set user state (no tokens)
    setUser({
      id: response.user.id,
      email: response.user.email,
      name: response.user.full_name,
      userType: response.user.user_type,
    });

    api.setRefreshTokenHandler(refreshAccessToken);
    api.setClearSessionHandler(clearSession);
  };

  const clearSession = async () => {
    await SecureStore.deleteItemAsync('accessToken');
    await SecureStore.deleteItemAsync('refreshToken');
    await SecureStore.deleteItemAsync('userData');
    api.clearToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout: clearSession, loading }}>
      {children}
    </AuthContext.Provider>
  );
};
```

---

### Phase 5: Mobile - Update WebSocketContext

**File**: `app/contexts/WebSocketContext.tsx`

Use `useToken` hook and Socket.IO's built-in ping/pong:

```typescript
import { useToken } from '@/hooks/useToken';

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const { user } = useAuth();
  const { isOnline } = useNetwork();
  const { token, loading: tokenLoading } = useToken();  // NEW

  const [isConnected, setIsConnected] = useState(false);
  const [socket, setSocket] = useState<Socket | null>(null);

  // Reconnects automatically when token changes!
  useEffect(() => {
    if (!user?.id || !isOnline || tokenLoading) {
      if (socket) {
        socket.close();
        setSocket(null);
      }
      setIsConnected(false);
      return;
    }

    if (!token) {
      if (socket) {
        socket.close();
        setSocket(null);
      }
      setIsConnected(false);
      return;
    }

    console.log('[WebSocket] Creating connection');

    if (socket) {
      socket.close();
    }

    const newSocket = io(baseUrl, {
      path: "/ws/socket.io",
      auth: { token },
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: 20,
      reconnectionDelay: 1000,
      // Built-in ping/pong (matches backend: 30s interval, 120s timeout)
      // Note: Client-side values are informational; server controls timing
    });

    newSocket.on('connect', () => {
      setIsConnected(true);
      console.log('[WebSocket] Connected:', newSocket.id);
    });

    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      console.log('[WebSocket] Disconnected:', reason);
    });

    // Optional: Log ping/pong for debugging
    newSocket.on('ping', () => {
      console.log('[WebSocket] Ping received');
    });

    newSocket.on('pong', (latency: number) => {
      console.log('[WebSocket] Pong received, latency:', latency, 'ms');
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [user?.id, isOnline, token, tokenLoading]);

  // ... event handlers remain the same
};
```

---

### Phase 6: Mobile - Update All API Call Sites

Remove `user.accessToken` parameter from all API calls.

**Files to Update**:
- `app/app/(tabs)/inbox.tsx`
- `app/hooks/chat/useTicketData.ts`
- `app/hooks/chat/useMessages.ts`
- `app/services/ticketSync.ts`
- All broadcast components

**Pattern**:

Before:
```typescript
const { user } = useAuth();
const tickets = await api.getTickets(user.accessToken, "open", 1);
```

After:
```typescript
const tickets = await api.getTickets("open", 1);
```

---

## Testing Strategy

### Manual Testing Checklist

#### Test 1: Token Refresh
- [ ] Login to app
- [ ] Set `ACCESS_TOKEN_EXPIRE_MINUTES=1` in backend
- [ ] Wait 2 minutes
- [ ] Fetch tickets
- [ ] Verify console: `[API] 401 error - attempting token refresh`
- [ ] Verify console: `[API] Token refresh successful`
- [ ] Verify API call succeeds

#### Test 2: WebSocket Reconnects on Token Refresh
- [ ] Login and connect WebSocket
- [ ] Wait for token expiration
- [ ] Verify console: `[useToken] Token changed`
- [ ] Verify console: `[WebSocket] Creating connection`
- [ ] Send message - should receive

#### Test 3: Multi-Device WebSocket
- [ ] Login Admin A on Device 1
- [ ] Login Admin B on Device 2
- [ ] Check backend logs: both in `ward:admin` and `user:{id}` rooms
- [ ] Send customer message
- [ ] Verify Device 1 receives instantly
- [ ] Verify Device 2 receives instantly

#### Test 4: Same User, Multiple Devices
- [ ] Login Admin A on Device 1
- [ ] Login Admin A on Device 2
- [ ] Check backend logs: 2 SIDs for same user_id
- [ ] Send message - both devices receive

#### Test 5: Socket.IO Ping/Pong
- [ ] Connect device
- [ ] Wait 40+ seconds
- [ ] Check mobile logs: "[WebSocket] Ping received" every 30s
- [ ] Check mobile logs: "[WebSocket] Pong received, latency: X ms"
- [ ] Connection remains stable
- [ ] Simulate network drop → Should reconnect within 120s

---

## Files Modified Summary

### Backend (3 files):
1. `backend/routers/auth.py` - Add refresh-mobile endpoint, add RefreshTokenRequest schema
2. `backend/schemas/user.py` - Add refresh_token field to TokenResponse
3. `backend/services/socketio_service.py` - Multi-device tracking + multi-room broadcasting + heartbeat

### Mobile (New - 2 files):
1. `app/utils/tokenEvents.ts` - Token event emitter
2. `app/hooks/useToken.ts` - Token reactive hook

### Mobile (Modified - 3+ core files):
1. `app/services/api.ts` - Token caching + event emission + remove token parameters
2. `app/contexts/AuthContext.tsx` - Remove token from state + wire up refresh
3. `app/contexts/WebSocketContext.tsx` - Use useToken hook + heartbeat

### Mobile (Modified - Multiple call sites):
- `app/app/(tabs)/inbox.tsx`
- `app/hooks/chat/useTicketData.ts`
- `app/hooks/chat/useMessages.ts`
- `app/services/ticketSync.ts`
- All broadcast components

### NO Changes Needed:
- ✅ `backend/routers/callbacks.py` - Calls emit functions (no changes)
- ✅ `backend/routers/whatsapp.py` - Calls emit functions (no changes)
- ✅ `backend/routers/messages.py` - Calls emit functions (no changes)
- ✅ `backend/routers/tickets.py` - Calls emit functions (no changes)

**Why?** All broadcasting logic is encapsulated in `socketio_service.py`.

---

## Expected Outcomes

After implementation:

1. ✅ **Multi-Device Support**: Multiple admins can connect simultaneously without conflicts
2. ✅ **Reliable Broadcasting**: Messages delivered via ward + user rooms (redundancy)
3. ✅ **Connection Health**: Heartbeat detects and recovers stale connections
4. ✅ **Token Refresh**: Mobile app automatically refreshes expired tokens
5. ✅ **WebSocket Reconnection**: Socket reconnects automatically on token change
6. ✅ **Comprehensive Logging**: Full visibility into connection lifecycle
7. ✅ **Secure Token Storage**: Tokens stored in SecureStore (encrypted)
8. ✅ **Clean API**: No token parameter in API calls

---

## Rollback Plan

If issues occur:

1. **Keep Backend Changes**: New `/auth/refresh-mobile` endpoint is backward compatible
2. **Revert Mobile API Client**: Restore token parameters if caching causes issues
3. **Revert Mobile AuthContext**: Restore token in user state if needed
4. **Keep WebSocket Diagnostics**: Enhanced logging helps debug issues
5. **Revert Multi-Room Broadcasting**: Can disable user-specific rooms if causing performance issues

---

## Additional Recommendations

1. **Redis Adapter** (future): For horizontal scaling with multiple backend instances
2. **Connection Metrics**: Track heartbeat latency, reconnection frequency
3. **Rate Limiting**: Limit heartbeat frequency per connection
4. **Token Rotation**: Rotate refresh tokens on each use (security enhancement)
5. **Monitoring Alerts**: Alert on high stale connection rates

---

## 📋 Implementation Checklist

### Backend Tasks
- [ ] Phase 1.1: Add RefreshTokenRequest schema to `backend/routers/auth.py`
- [ ] Phase 1.2: Add `/auth/refresh-mobile` endpoint
- [ ] Phase 1.3: Update TokenResponse schema in `backend/schemas/user.py`
- [ ] Phase 1.4: Update login endpoint to include refresh_token
- [ ] Phase 2.1: Replace USER_CACHE with USER_CONNECTIONS in `socketio_service.py`
- [ ] Phase 2.2: Update connect() handler with user-specific rooms
- [ ] Phase 2.3: Update disconnect() handler
- [ ] Phase 2.4: Verify Socket.IO ping/pong in `backend/services/socketio_service.py` (already configured)
- [ ] Phase 2.5: Update emit_message_received() with multi-room broadcasting
- [ ] Phase 2.6: Update emit_whisper_created() with multi-room broadcasting
- [ ] Phase 2.7: Update emit_ticket_resolved() with multi-room broadcasting

### Mobile Tasks
- [ ] Phase 3.1: Create `app/utils/tokenEvents.ts`
- [ ] Phase 3.2: Create `app/hooks/useToken.ts`
- [ ] Phase 3.3: Update `app/services/api.ts` with token caching and refreshTokenMobile()
- [ ] Phase 4: Update `app/contexts/AuthContext.tsx` (remove token from state)
- [ ] Phase 5: Update `app/contexts/WebSocketContext.tsx` (use useToken + heartbeat)
- [ ] Phase 6.1: Update `app/app/(tabs)/inbox.tsx` (remove token params)
- [ ] Phase 6.2: Update `app/hooks/chat/useTicketData.ts` (remove token params)
- [ ] Phase 6.3: Update `app/hooks/chat/useMessages.ts` (remove token params)
- [ ] Phase 6.4: Update `app/services/ticketSync.ts` (remove token params)
- [ ] Phase 6.5: Update all broadcast components (remove token params)

### Testing Tasks
- [ ] Test 1: Token refresh on mobile
- [ ] Test 2: WebSocket reconnects on token refresh
- [ ] Test 3: Multi-device WebSocket (different admins)
- [ ] Test 4: Same user on multiple devices
- [ ] Test 5: Socket.IO ping/pong mechanism (check logs for ping/pong events)
- [ ] Integration test: Full flow with expired token
- [ ] Load test: 10+ concurrent admin connections

---

## ✅ Success Criteria

1. **Multiple admin users can connect from different devices** without any connection conflicts or dropped messages
2. **Same admin user can connect from multiple devices** (e.g., phone + tablet) and receive messages on all devices
3. **All real-time events reach all intended recipients** (tickets, messages, whispers, resolutions)
4. **Token automatically refreshes on mobile** when access token expires (no forced logout)
5. **WebSocket reconnects automatically** when token is refreshed (seamless user experience)
6. **Socket.IO ping/pong detects stale connections** and triggers reconnection within 60 seconds
7. **Backend logs show complete connection lifecycle** (connect, rooms joined, heartbeat, disconnect)
8. **Mobile app stores tokens securely** in expo-secure-store (encrypted)
9. **API client caches token** and removes need for token parameter in every call
10. **No breaking changes** to existing functionality (backward compatible)

---

## 📚 Example Scenarios

### Scenario 1: Token Refresh During Active Session

**Setup:**
- Admin A logged in on mobile device
- access_token expires in 1 minute (testing config)
- User is viewing inbox

**Flow:**
```
1. User opens inbox → API call succeeds ✅
2. Wait 2 minutes (token expires)
3. User pulls to refresh inbox
4. API client detects 401 error
   Log: "[API] 401 error - attempting token refresh"
5. API client calls refreshTokenMobile()
6. Backend validates refresh_token → returns new access_token
7. API client saves to SecureStore
8. API client caches token and emits TOKEN_CHANGED
9. API client retries original request → succeeds ✅
   Log: "[API] Token refresh successful"
10. useToken hook detects change
11. WebSocket reconnects with new token
    Log: "[WebSocket] Creating connection"
12. User continues working seamlessly ✅
```

**Expected:**
- No forced logout
- Brief reconnection (< 2 seconds)
- All subsequent API calls work
- WebSocket reconnects automatically

### Scenario 2: Multi-Device Message Broadcasting

**Setup:**
- Admin A (user_id: 1) on Device 1 (iPhone)
- Admin B (user_id: 2) on Device 2 (Android)
- Customer sends message to ticket in Ward 5

**Flow:**
```
1. Customer sends WhatsApp message
2. Backend creates message in database
3. Backend calls emit_message_received()
4. Backend identifies admins:
   - Admin A (user_id: 1) - 1 active connection (sid_abc123)
   - Admin B (user_id: 2) - 1 active connection (sid_xyz789)
5. Backend broadcasts to multiple rooms:
   a. ward:admin → [sid_abc123, sid_xyz789]
   b. user:1 → [sid_abc123]
   c. user:2 → [sid_xyz789]
6. Device 1 receives via ward:admin (primary path) ✅
7. Device 2 receives via ward:admin (primary path) ✅
8. Redundant delivery via user-specific rooms (backup) ✅
   Log: "[EMIT:TICKETS] message_received broadcast complete - rooms: 3, direct users: 2"
9. Both devices show new message notification
10. Both inboxes update with unread count
```

**Expected:**
- Both admins receive message instantly (< 500ms)
- No duplicate messages (deduplication in client)
- Backend logs show successful broadcast to all rooms

### Scenario 3: Same User, Multiple Devices

**Setup:**
- Admin A (user_id: 1) on Device 1 (iPhone)
- Admin A (user_id: 1) on Device 2 (iPad)
- Customer sends message

**Flow:**
```
1. Device 1 connects:
   Log: "[CONNECTIONS] Added: user 1 -> sid_abc123 (total sessions: 1)"
2. Device 2 connects:
   Log: "[CONNECTIONS] Added: user 1 -> sid_def456 (total sessions: 2)"
3. Backend tracks:
   USER_CONNECTIONS[1] = {sid_abc123, sid_def456}
4. Customer sends message
5. Backend broadcasts:
   - ward:admin → [sid_abc123, sid_def456]
   - user:1 → [sid_abc123, sid_def456]
6. Device 1 receives ✅
7. Device 2 receives ✅
8. Both devices show notification
```

**Expected:**
- Both devices receive message simultaneously
- No connection conflict (old behavior would disconnect Device 1)
- Backend logs show 2 sessions for user 1

---

## 🔧 Troubleshooting

### Issue: Token refresh fails with "Refresh token required"

**Symptoms:**
- API call returns 401 after token expires
- Console: "Token refresh failed"

**Diagnosis:**
```typescript
// Check SecureStore
const refreshToken = await SecureStore.getItemAsync('refreshToken');
console.log('Refresh token exists:', !!refreshToken);
```

**Solutions:**
1. Verify backend login endpoint includes `refresh_token` in response
2. Verify mobile AuthContext saves refresh_token to SecureStore
3. Check backend logs for token validation errors

### Issue: WebSocket doesn't reconnect after token refresh

**Symptoms:**
- Token refreshes successfully
- Console: "[API] Token refresh successful"
- But no WebSocket reconnection message

**Diagnosis:**
```typescript
// Add debug logging to useToken hook
console.log('[useToken] Current token:', token);
console.log('[useToken] Token loading:', loading);
```

**Solutions:**
1. Verify tokenEmitter emits TOKEN_CHANGED event after refresh
2. Verify useToken hook subscribes to TOKEN_CHANGED events
3. Check WebSocketContext effect dependencies include `token`

### Issue: Multiple devices receive duplicate messages

**Symptoms:**
- Message appears 2-3 times in inbox/chat

**Diagnosis:**
```typescript
// Check message deduplication in inbox.tsx
console.log('[Inbox] Message already exists, skipping');
```

**Solutions:**
1. Verify client checks `m.id` before adding message (lines 112-136 in useChatWebSocket.ts)
2. Add unique key check in FlatList (`keyExtractor={(item) => String(item.id)}`)

### Issue: Ping/Pong timeout causes frequent disconnections

**Symptoms:**
- Console: "[WebSocket] Disconnected: ping timeout"
- Socket reconnects repeatedly

**Diagnosis:**
```typescript
// Check if ping/pong events are firing
newSocket.on('ping', () => console.log('Ping'));
newSocket.on('pong', (latency) => console.log('Pong:', latency));
```

**Solutions:**
1. Verify backend has `ping_interval` and `ping_timeout` configured
2. Check network stability (poor connection = pong timeouts)
3. Increase `pingTimeout` if needed (e.g., 90000 for slower networks)
4. Verify mobile app isn't going into background (React Native suspends timers)

### Issue: Backend logs show "User has no more connections" prematurely

**Symptoms:**
- Backend: "[CONNECTIONS] User 1 has no more connections"
- But user still viewing app

**Diagnosis:**
```python
# Check disconnect handler
logger.info(f"[DISCONNECT] User {user_id}, duration: {duration}")
```

**Solutions:**
1. Check mobile app isn't creating multiple socket instances
2. Verify WebSocketContext cleanup in useEffect return
3. Check heartbeat interval isn't causing disconnections

---

## 🚀 Future Enhancements

### 1. Redis Adapter for Horizontal Scaling
**Problem:** Multiple backend instances don't share socket connections
**Solution:** Add Redis adapter to Socket.IO
```python
# backend/services/socketio_service.py
import socketio

redis_manager = socketio.AsyncRedisManager('redis://redis:6379')
sio_server = socketio.AsyncServer(
    client_manager=redis_manager,
    cors_allowed_origins="*"
)
```

### 2. Connection Metrics Dashboard
**Problem:** No visibility into connection health trends
**Solution:** Track metrics in database
- Average heartbeat latency per user
- Reconnection frequency
- Peak concurrent connections
- Failed connection attempts

### 3. Automatic Token Rotation
**Problem:** Refresh token stolen → attacker has indefinite access
**Solution:** Rotate refresh token on each use
```python
# backend/routers/auth.py
@router.post("/refresh-mobile")
def refresh_token_mobile(request: RefreshTokenRequest):
    # ... validate old refresh_token ...

    # Generate NEW refresh token
    new_refresh_token = create_refresh_token(data={"sub": email})

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token  # Rotate!
    }
```

### 4. Push Notification Fallback
**Problem:** WebSocket disconnected → user misses messages
**Solution:** Send push notification if WebSocket delivery fails
```python
# backend/services/socketio_service.py
async def emit_with_fallback(event, data, room):
    # Emit to WebSocket
    await sio_server.emit(event, data, room=room)

    # Check if delivered
    delivered = await check_socket_receipt(room)

    if not delivered:
        # Fallback to push notification
        await push_service.send_notification(data)
```

### 5. Selective Room Sync
**Problem:** Admin only cares about Ward 5, receives updates for all wards
**Solution:** Subscribe only to relevant ward rooms
```python
# Mobile app sends preference
socket.emit('subscribe_wards', { ward_ids: [5, 12] })

# Backend joins only those rooms
@sio_server.event
async def subscribe_wards(sid, data):
    for ward_id in data['ward_ids']:
        await sio_server.enter_room(sid, f"ward:{ward_id}")
```

---

## ⏱️ Estimated Effort

### Development Time
- **Phase 1 (Backend Token Refresh):** 2 hours
  - 1 hour: Implement endpoint + schema
  - 1 hour: Testing + edge cases

- **Phase 2 (Backend WebSocket):** 4 hours
  - 2 hours: Multi-device tracking + rooms
  - 1 hour: Heartbeat mechanism
  - 1 hour: Multi-room broadcasting

- **Phase 3-5 (Mobile Token Management):** 6 hours
  - 2 hours: Token infrastructure (events, hook, API client)
  - 2 hours: AuthContext refactor
  - 1 hour: WebSocketContext updates
  - 1 hour: Testing

- **Phase 6 (Update Call Sites):** 3 hours
  - Search and replace token parameters
  - Test each screen

**Total Development:** ~15 hours (2 developer days)

### Testing Time
- **Manual Testing:** 4 hours
- **Integration Testing:** 3 hours
- **Multi-Device Testing:** 2 hours

**Total Testing:** ~9 hours (1 developer day)

### **Grand Total:** ~24 hours (3 developer days)

---

## 📊 Deployment Strategy

### Phase 1: Backend Only (Low Risk)
1. Deploy backend with new `/auth/refresh-mobile` endpoint
2. Update TokenResponse schema
3. Monitor logs for errors
4. **Risk:** Low (backward compatible)

### Phase 2: Backend WebSocket (Medium Risk)
1. Deploy updated socketio_service.py with multi-device support
2. Existing clients continue working (ward:admin rooms still used)
3. Monitor connection counts and heartbeat logs
4. **Risk:** Medium (affects real-time communication)

### Phase 3: Mobile App (High Risk)
1. Deploy updated mobile app with token management
2. Test with small group of admins first (beta testing)
3. Monitor token refresh success rate
4. Monitor WebSocket reconnection logs
5. **Risk:** High (affects authentication flow)

### Rollback Plan
- Backend: Keep changes (backward compatible)
- Mobile: Revert to previous version if critical issues
- WebSocket: Can disable user-specific rooms via feature flag

---

## 📖 References

### Socket.IO Documentation
- **Rooms (Multi-Device)**: https://socket.io/docs/v4/rooms/
- **Server Options (pingInterval/pingTimeout)**: https://socket.io/docs/v4/server-options/
- **How it Works (Ping/Pong Mechanism)**: https://socket.io/docs/v4/how-it-works/
- **Engine.IO Protocol (Heartbeat)**: https://socket.io/docs/v4/engine-io-protocol/
- **Client Initialization (Reconnection)**: https://socket.io/docs/v4/client-initialization/#reconnection

### Expo/React Native
- **Expo SecureStore**: https://docs.expo.dev/versions/latest/sdk/securestore/
- **React Native Token Management**: Best practices for secure token storage

### Community Resources
- **Stack Overflow: Does Socket.IO handle ping pong automatically?**: https://stackoverflow.com/questions/66594002/does-socket-io-handle-ping-pong-automatically
- **Stack Overflow: Default pingTimeout and pingInterval values**: https://stackoverflow.com/questions/50259472/what-is-the-default-pingtimeout-and-pinginterval-in-socket-io

---

**Status:** ✅ Ready for implementation
