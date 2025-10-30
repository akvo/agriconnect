# Admin Chat Playground - Implementation Plan

## Overview
Create a sophisticated admin-only playground for testing and fine-tuning AI service prompts. This feature allows admins to experiment with custom prompts, view active service configurations, and test conversations without affecting production data.

## Architecture Overview

This feature uses **async job pattern with WebSocket notifications**:

1. **Admin sends message** → POST `/api/admin/playground/chat`
2. **Backend creates AI job** → Sends to external AI service with `source: "playground"` flag
3. **Returns immediately** → Response includes `job_id` and `pending` status
4. **AI processes async** → Takes 2-10 seconds
5. **AI calls back** → POST `/api/callback/ai` with `source: "playground"` in callback_params
6. **Backend handles callback** → Stores response, emits WebSocket event to `playground:{session_id}` room
7. **Frontend receives event** → Updates UI with AI response in real-time

This reuses existing infrastructure (ExternalAIService, Socket.IO) while keeping playground data isolated.

---

## 1. Backend Implementation

### 1.1 Database Model
**File**: `/backend/models/playground_message.py`

Create new model `PlaygroundMessage`:
```python
- id: Integer (Primary Key)
- admin_user_id: Integer (Foreign Key → admin_users.id)
- session_id: String (UUID, indexed for fast queries)
- role: String (enum: 'user', 'assistant')
- content: Text (message content)
- job_id: String (nullable, AI job ID for tracking async processing)
- status: String (nullable, 'pending', 'completed', 'failed' - for assistant messages only)
- custom_prompt: Text (nullable, stores overridden prompt if used)
- service_used: String (name of active service at time of message)
- response_time_ms: Integer (nullable, AI response time in milliseconds)
- created_at: DateTime (auto timestamp)
- updated_at: DateTime (auto timestamp on update)
```

**Relationships**:
- Many-to-one with `AdminUser`
- Grouped by `session_id` for conversation threads

**Status Field**:
- User messages: `status` is always NULL
- Assistant messages:
  - `pending` when job created
  - `completed` when callback received
  - `failed` if AI service errors

### 1.2 Database Migration
**File**: `/backend/alembic/versions/XXXX_add_playground_message.py`

- Create `playground_messages` table
- Add foreign key constraint to `admin_users`
- Create index on `session_id` for performance
- Create index on `admin_user_id` and `created_at` for queries

### 1.3 API Router
**File**: `/backend/routers/admin_playground.py` (new file)

**Endpoints**:

#### `GET /api/admin/playground/active-service`
- Returns active service configuration
- Response:
  ```json
  {
    "service_name": "string",
    "chat_url": "string",
    "is_active": true,
    "has_valid_token": true
  }
  ```
- Sanitize sensitive data (don't expose full tokens)

#### `POST /api/admin/playground/chat`
- Send message with optional custom prompt (async with WebSocket notification)
- Request:
  ```json
  {
    "message": "string",
    "session_id": "uuid (optional)",
    "custom_prompt": "string (optional)"
  }
  ```
- Response (immediate):
  ```json
  {
    "session_id": "uuid",
    "user_message": {PlaygroundMessage},
    "job_id": "ai_job_12345",
    "status": "pending"
  }
  ```
- Logic:
  1. Generate/validate session_id
  2. Store user message
  3. Get active service configuration
  4. Create AI job with ExternalAIService.create_chat_job()
     - Include `source: "playground"` in callback_params
     - Include `session_id` and `admin_user_id` in callback_params
     - Use custom_prompt if provided, else default_prompt
  5. Store pending assistant message with job_id
  6. Return immediately (don't wait for AI)
  7. AI will callback later → triggers WebSocket event

#### `GET /api/admin/playground/history`
- Get conversation history for a session
- Query params:
  - `session_id` (required)
  - `limit` (optional, default 100)
  - `offset` (optional, default 0)
- Response:
  ```json
  {
    "session_id": "uuid",
    "messages": [PlaygroundMessage],
    "total_count": 42
  }
  ```

#### `GET /api/admin/playground/sessions`
- List all sessions for current admin user
- Query params:
  - `limit` (optional, default 20)
  - `offset` (optional, default 0)
- Response:
  ```json
  {
    "sessions": [
      {
        "session_id": "uuid",
        "message_count": 10,
        "created_at": "timestamp",
        "last_message_at": "timestamp"
      }
    ],
    "total_count": 5
  }
  ```

#### `DELETE /api/admin/playground/session/{session_id}`
- Delete all messages in a session
- Verify session belongs to authenticated admin user
- Response: `204 No Content`

#### `GET /api/admin/playground/default-prompt`
- Get the current default prompt from admin settings
- Response:
  ```json
  {
    "default_prompt": "string"
  }
  ```

### 1.4 Callback Schema Update
**File**: `/backend/schemas/callback.py`

Update `CallbackParams` to support playground callbacks:
```python
class CallbackParams(BaseModel):
    message_id: int
    message_type: Optional[int] = None
    customer_id: Optional[int] = None
    ticket_id: Optional[int] = None
    administrative_id: Optional[int] = None

    # Playground-specific fields
    source: Optional[str] = None  # "playground" or None (production)
    session_id: Optional[str] = None  # UUID for playground session
    admin_user_id: Optional[int] = None  # Admin user ID
```

### 1.5 Callback Handler
**File**: `/backend/routers/callbacks.py` (modify existing)

Update `ai_callback()` function to detect and handle playground callbacks:

```python
async def ai_callback(payload: AIWebhookCallback, db: Session):
    # Check if this is a playground callback
    if (payload.callback_params and
        payload.callback_params.source == "playground"):
        return await handle_playground_callback(payload, db)

    # Existing production logic...
    return await handle_production_callback(payload, db)

async def handle_playground_callback(payload, db):
    """Handle AI callbacks for playground messages"""
    if payload.status != CallbackStage.COMPLETED or not payload.output:
        # Handle error case
        # Update playground message status to 'failed'
        return {"status": "error"}

    # Get playground message by job_id
    from models.playground_message import PlaygroundMessage
    pg_message = db.query(PlaygroundMessage).filter(
        PlaygroundMessage.job_id == payload.job_id,
        PlaygroundMessage.role == 'assistant'
    ).first()

    if not pg_message:
        logger.warning(f"Playground message not found for job {payload.job_id}")
        return {"status": "received"}

    # Calculate response time
    import time
    response_time_ms = int((time.time() - pg_message.created_at.timestamp()) * 1000)

    # Update message with AI response
    pg_message.content = payload.output.answer
    pg_message.status = 'completed'
    pg_message.response_time_ms = response_time_ms
    pg_message.updated_at = datetime.utcnow()
    db.commit()

    # Emit WebSocket event to playground room
    from routers.ws import emit_playground_response
    session_id = payload.callback_params.session_id
    await emit_playground_response(
        session_id=session_id,
        message_id=pg_message.id,
        content=pg_message.content,
        response_time_ms=response_time_ms
    )

    return {"status": "received", "job_id": payload.job_id}
```

### 1.6 WebSocket Integration
**File**: `/backend/routers/ws.py` (modify existing)

Add playground room support and emit function:

```python
# Add to existing Socket.IO server

async def emit_playground_response(
    session_id: str,
    message_id: int,
    content: str,
    response_time_ms: int
):
    """
    Emit playground_response event to playground session room.
    Called when AI callback completes for playground message.
    """
    event_data = {
        "session_id": session_id,
        "message_id": message_id,
        "content": content,
        "response_time_ms": response_time_ms,
        "role": "assistant",
        "status": "completed"
    }

    # Emit to playground session room
    room_name = f"playground:{session_id}"
    await sio.emit("playground_response", event_data, room=room_name)

    logger.info(
        f"Emitted playground_response event for session {session_id}, "
        f"message {message_id}"
    )

# Export
__all__ = [
    # ... existing exports
    "emit_playground_response",
]
```

**Note**: Admin users will join `playground:{session_id}` room when they open the playground page. This uses the existing Socket.IO infrastructure.

### 1.7 Authentication & Authorization
- All endpoints require JWT authentication
- Verify user has admin role (`is_admin=True`)
- Users can only access their own playground sessions

---

## 2. Frontend Implementation

### 2.1 Admin Navigation
**File**: `/frontend/src/components/AdminLayout.tsx` or similar

Add new navigation item:
- Label: "Chat Playground"
- Icon: Beaker/Flask icon from Heroicons
- Route: `/admin/playground`

### 2.2 Main Playground Page
**File**: `/frontend/src/app/admin/playground/page.tsx`

**Layout Structure** (3-column grid):
```
┌─────────────────┬──────────────────────┬─────────────────┐
│                 │                      │                 │
│  Left Panel     │   Center Panel       │  Right Panel    │
│  (Config)       │   (Chat)             │  (Sessions)     │
│                 │                      │                 │
│  - Service Info │   - Messages         │  - Session List │
│  - Prompt       │   - Input            │  - Controls     │
│    Override     │                      │                 │
│                 │                      │                 │
└─────────────────┴──────────────────────┴─────────────────┘
```

**State Management**:
```typescript
- activeService: ServiceConfig | null
- defaultPrompt: string
- customPrompt: string
- currentSessionId: string | null
- messages: PlaygroundMessage[]
- sessions: SessionSummary[]
- isLoading: boolean
- isSending: boolean
- socket: Socket | null  // Socket.IO connection
- isConnected: boolean   // WebSocket connection status
```

**WebSocket Integration**:
- Connect to Socket.IO on page load
- Join `playground:{session_id}` room
- Listen for `playground_response` event
- Update messages array when response arrives
- Show connection status indicator

### 2.3 Left Panel Component
**File**: `/frontend/src/components/playground/ConfigPanel.tsx`

**Features**:
1. **Active Service Display**
   - Service name badge
   - Status indicator (green dot if active)
   - Service URLs (chat, upload)
   - Last updated timestamp

2. **Prompt Override Section**
   - Label: "Custom Prompt (Override)"
   - Large textarea (min 200px height)
   - Character count
   - "Use Default" button to clear override
   - "Reset" button to restore to default prompt

3. **Default Prompt Reference**
   - Collapsible section
   - Read-only view of current default prompt
   - Copy button

4. **Diff Viewer** (optional enhancement)
   - Show visual diff between default and custom prompt
   - Highlight changes in red/green

### 2.4 Center Panel Component
**File**: `/frontend/src/components/playground/ChatPanel.tsx`

**Features**:
1. **Message Display Area**
   - Scrollable container
   - Message bubbles:
     - User messages: right-aligned, blue
     - Assistant messages: left-aligned, gray
   - Each message shows:
     - Content (with markdown rendering)
     - Timestamp
     - Copy button
     - Badge if custom prompt was used
     - Response time (for assistant messages)

2. **Message Input Area**
   - Textarea for typing message
   - Send button (with loading state)
   - Keyboard shortcut: Cmd/Ctrl + Enter to send
   - Character limit indicator

3. **Special Features**:
   - Auto-scroll to latest message
   - Loading indicator when waiting for response (show "pending" state)
   - Code syntax highlighting in messages
   - Markdown rendering support
   - Show "..." typing indicator for pending assistant messages

### 2.5 WebSocket Client Integration
**File**: `/frontend/src/hooks/usePlaygroundSocket.ts`

Custom React hook for WebSocket connection:

```typescript
import { useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';

export function usePlaygroundSocket(sessionId: string | null, onResponse: (data: any) => void) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!sessionId) return;

    // Connect to Socket.IO
    const token = localStorage.getItem('token'); // Get JWT token
    const newSocket = io('http://localhost:8000/ws', {
      auth: { token },
      transports: ['websocket']
    });

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket');
      setIsConnected(true);

      // Join playground session room
      const roomName = `playground:${sessionId}`;
      newSocket.emit('join_room', { room: roomName });
    });

    newSocket.on('disconnect', () => {
      console.log('Disconnected from WebSocket');
      setIsConnected(false);
    });

    // Listen for playground responses
    newSocket.on('playground_response', (data) => {
      console.log('Received playground response:', data);
      onResponse(data);
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [sessionId, onResponse]);

  return { socket, isConnected };
}
```

**Usage in page**:
```typescript
const handlePlaygroundResponse = useCallback((data: any) => {
  // Update message in messages array from 'pending' to completed
  setMessages(prev => prev.map(msg =>
    msg.id === data.message_id
      ? { ...msg, content: data.content, status: 'completed', response_time_ms: data.response_time_ms }
      : msg
  ));
}, []);

const { socket, isConnected } = usePlaygroundSocket(currentSessionId, handlePlaygroundResponse);
```

### 2.6 Right Panel Component
**File**: `/frontend/src/components/playground/SessionPanel.tsx`

**Features**:
1. **Session List**
   - List of previous sessions
   - Each session shows:
     - Session ID (truncated)
     - Message count
     - Created date
     - Click to load session

2. **Controls**
   - "New Session" button
   - "Clear Current Session" button (with confirmation)
   - "Export Conversation" button (download as JSON/MD)

3. **Session Actions**
   - Load session (changes current view)
   - Delete session (with confirmation dialog)

### 2.7 API Client
**File**: `/frontend/src/lib/api/playground.ts`

**Functions**:
```typescript
- getActiveService(): Promise<ServiceConfig>
- getDefaultPrompt(): Promise<string>
- sendChat(params): Promise<ChatResponse>  // Returns immediately with job_id
- getHistory(sessionId, params): Promise<HistoryResponse>
- getSessions(params): Promise<SessionsResponse>
- deleteSession(sessionId): Promise<void>
```

**Note**: `sendChat()` returns immediately with `job_id` and `status: "pending"`. The actual AI response arrives via WebSocket event.

### 2.8 Types
**File**: `/frontend/src/types/playground.ts`

Define TypeScript interfaces:
```typescript
interface ServiceConfig {
  service_name: string;
  chat_url: string;
  is_active: boolean;
  has_valid_token: boolean;
}

interface PlaygroundMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  job_id: string | null;
  status: 'pending' | 'completed' | 'failed' | null;
  custom_prompt: string | null;
  service_used: string;
  response_time_ms: number | null;
  created_at: string;
  updated_at: string;
}

interface SessionSummary {
  session_id: string;
  message_count: number;
  created_at: string;
  last_message_at: string;
}
```

---

## 3. Testing Strategy

### 3.1 Backend Tests
**File**: `/backend/tests/test_admin_playground.py`

Test cases:
- ✓ Create playground message
- ✓ Get active service configuration
- ✓ Send chat with default prompt
- ✓ Send chat with custom prompt override
- ✓ Get chat history for session
- ✓ Get user's sessions list
- ✓ Delete session
- ✓ Authorization: non-admin cannot access
- ✓ Authorization: admin can only access own sessions
- ✓ Handle missing active service gracefully
- ✓ Track response time correctly

### 3.2 Frontend Tests
**File**: `/frontend/src/app/admin/playground/__tests__/`

Test cases:
- ✓ Render playground page
- ✓ Display active service info
- ✓ Send message successfully
- ✓ Display messages in correct order
- ✓ Override prompt functionality
- ✓ Load previous sessions
- ✓ Clear session with confirmation
- ✓ Export conversation
- ✓ Handle API errors gracefully

### 3.3 Integration Testing
- Full flow: Login → Navigate to playground → Send messages → Override prompt → Clear session
- Test with different AI services configured
- Test with no active service
- Test session persistence across page refreshes

---

## 4. Implementation Order

1. **Backend Foundation** (Tasks 1-2)
   - Create database model with `job_id`, `status`, `updated_at` fields
   - Generate and run migration

2. **Backend Callback Infrastructure** (Tasks 3-5)
   - Update callback schema to support `source`, `session_id`, `admin_user_id` fields
   - Add playground callback handler in `/api/callback/ai`
   - Add WebSocket emit function `emit_playground_response()` in `ws.py`

3. **Backend API Endpoints** (Tasks 6-9)
   - Active service configuration endpoint
   - Chat endpoint (creates AI job, returns immediately with pending status)
   - History endpoint
   - Sessions list endpoint
   - Delete session endpoint

4. **Frontend Structure** (Task 10)
   - Create main page with layout
   - Set up routing and navigation

5. **Frontend Components** (Tasks 11-13)
   - Chat interface with pending/completed states
   - Prompt override panel
   - Service settings display panel

6. **WebSocket Integration** (Task 14)
   - Create `usePlaygroundSocket` custom hook
   - Connect to Socket.IO and join playground room
   - Listen for `playground_response` events
   - Update messages from pending to completed

7. **Polish & Testing** (Tasks 15-16)
   - Add clear/reset functionality
   - End-to-end testing with real AI service
   - Bug fixes and refinements

---

## 5. Future Enhancements (Optional)

- **Streaming Responses**: Stream AI tokens in real-time (like ChatGPT typing effect)
- **Prompt Library**: Save and reuse custom prompts
- **Comparison Mode**: Run same message with different prompts side-by-side
- **Analytics**: Track which prompts perform better
- **Share Sessions**: Export and share playground conversations with team
- **A/B Testing**: Compare responses from different AI services
- **Prompt Templates**: Pre-defined prompt variations for common scenarios
- **Collaborative Testing**: Allow multiple admins to share playground sessions
- **Feedback System**: Rate and annotate AI responses for quality tracking
- **Chat History Context**: Include previous messages as context in AI requests

---

## 6. Technical Considerations

### Security
- All endpoints protected by JWT authentication
- Admin-only access verification on every request
- Session isolation (admins can only access own sessions)
- Sanitize service configuration in API responses (hide tokens)
- Validate and sanitize user inputs to prevent injection attacks

### Performance
- Index on `session_id` for fast conversation retrieval
- Pagination for long conversation histories
- Lazy loading for session list
- Response time tracking for performance monitoring
- Cache default prompt to reduce database queries

### User Experience
- Auto-save draft messages in localStorage
- Keyboard shortcuts for common actions
- Real-time typing indicators (optional)
- Toast notifications for actions (saved, deleted, etc.)
- Mobile-responsive design
- Dark mode support

### Data Management
- Soft delete option for sessions (keep for analytics)
- Automatic cleanup of old playground sessions (configurable retention)
- Export formats: JSON, Markdown, CSV
- Import previous conversations (optional)

---

## 7. Database Schema

```sql
CREATE TABLE playground_messages (
    id SERIAL PRIMARY KEY,
    admin_user_id INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    job_id VARCHAR(100),  -- AI job ID for async tracking
    status VARCHAR(20) CHECK (status IN ('pending', 'completed', 'failed')),  -- NULL for user messages
    custom_prompt TEXT,
    service_used VARCHAR(100),
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_playground_session ON playground_messages(session_id);
CREATE INDEX idx_playground_admin_user ON playground_messages(admin_user_id, created_at DESC);
CREATE INDEX idx_playground_job ON playground_messages(job_id) WHERE job_id IS NOT NULL;
```

**Notes**:
- `job_id` and `status` are only used for assistant messages
- User messages have `job_id = NULL` and `status = NULL`
- Assistant messages start with `status = 'pending'`, updated to `'completed'` or `'failed'` via callback

---

## 8. API Examples

### Send Chat Message
```bash
curl -X POST http://localhost:8000/api/admin/playground/chat \
  -H "Authorization: Bearer <admin_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the best practices for crop rotation?",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "custom_prompt": "You are an agricultural expert specializing in sustainable farming practices."
  }'
```

### Get Session History
```bash
curl -X GET "http://localhost:8000/api/admin/playground/history?session_id=550e8400-e29b-41d4-a716-446655440000&limit=50" \
  -H "Authorization: Bearer <admin_jwt_token>"
```

### Get Active Service
```bash
curl -X GET http://localhost:8000/api/admin/playground/active-service \
  -H "Authorization: Bearer <admin_jwt_token>"
```

### Delete Session
```bash
curl -X DELETE http://localhost:8000/api/admin/playground/session/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <admin_jwt_token>"
```

---

## Implementation Status

**Backend:**
- [ ] Database model created with `job_id`, `status`, `updated_at`
- [ ] Database migration generated and applied
- [ ] Callback schema updated (`source`, `session_id`, `admin_user_id`)
- [ ] Playground callback handler in `/api/callback/ai`
- [ ] WebSocket emit function `emit_playground_response()`
- [ ] API endpoint: active-service (GET)
- [ ] API endpoint: chat (POST) - async with job creation
- [ ] API endpoint: history (GET)
- [ ] API endpoint: sessions (GET)
- [ ] API endpoint: default-prompt (GET)
- [ ] API endpoint: delete session (DELETE)

**Frontend:**
- [ ] Main playground page with 3-panel layout
- [ ] Left panel (service info & prompt override)
- [ ] Center panel (chat interface with pending states)
- [ ] Right panel (session management)
- [ ] WebSocket hook (`usePlaygroundSocket`)
- [ ] Socket.IO connection and room joining
- [ ] Listen for `playground_response` events
- [ ] API client integration
- [ ] TypeScript types defined

**Testing:**
- [ ] Backend unit tests
- [ ] Frontend component tests
- [ ] WebSocket integration tests
- [ ] End-to-end testing with real AI service
- [ ] Documentation complete

---

**Last Updated**: 2025-10-30
**Feature Branch**: `feature/48-admin-chat-playground`
**Architecture**: Async job pattern with WebSocket notifications (reuses existing ExternalAIService + Socket.IO)
