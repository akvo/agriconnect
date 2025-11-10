# EO/Admin Messaging Bug Fix: Admin/EO Messages Not Appearing

**Date:** 2025-11-07
**Author:** AgriConnect Team
**Status:** In Progress
**Objective:** Fix real-time messaging system where messages sent by EO/admin users don't appear immediately in the chat UI due to missing sender identification in WebSocket event payload

---

## 📊 Problem Analysis

### Issue Description

Messages sent by Extension Officers (EO) or other admin users on the same ticket don't appear immediately in the chat UI on the mobile app.

### Current Behavior

**Log Output from Mobile App:**
```
LOG  [Chat] Received new message: {
  "body": "Sorry. Your question is OOT",
  "customer_id": 4,
  "customer_name": "+6281393504913",  // ❌ Shows phone number, not sender name
  "from_source": 2,                     // Admin/EO message
  "message_id": 71,
  "phone_number": "+6281393504913",
  "ticket_id": 12,
  "ticket_number": "20251107071917",
  "ts": "2025-11-07T07:38:05.977947+00:00"
  // ❌ Missing user_id field
}
```

### Root Causes

1. **Missing Sender ID:** The WebSocket event payload lacks a `user_id` field to identify who sent the message
2. **Confusing Field Name:** The `customer_name` field is semantically unclear and contains the ticket customer's phone number instead of the actual sender's name
3. **Display Logic Limitation:** Mobile app can't distinguish between different admin senders without proper identification

### Impact

- Admin/EO messages either don't display or show incorrect sender names
- Multi-user collaboration on tickets is broken
- User experience degraded for Extension Officers

---

## 🎯 Solution Design

### Conditional Payload Strategy

To maintain constant payload size while providing semantic clarity:

| Message Source | Field Included | Value |
|----------------|----------------|-------|
| **Admin/EO** (from_source=2) | `user_id` | Sender's user ID |
| **Customer** (from_source=1) | `customer_id` | Customer's ID |
| **LLM** (from_source=3) | `customer_id` | Customer's ID (ticket context) |

**Bandwidth Impact:** Zero (same number of fields, different names based on context)

### Sender Name Field Strategy

**Key Change:** Rename `customer_name` → `sender_name` for semantic clarity.

| Message Source | `sender_name` Value |
|----------------|---------------------|
| **Admin/EO** (from_source=2) | Sender's `full_name` from user table (e.g., "John Doe") |
| **Customer** (from_source=1) | Customer's `full_name` or phone number (existing logic) |
| **LLM** (from_source=3) | "WHISPER" for AI suggestions |

**Rationale:** The field name `sender_name` accurately represents who/what sent the message. For LLM messages, the sender is the AI system (WHISPER), not the customer.

### Data Flow

#### Before Fix ❌
```
Backend Event:
{
  customer_name: "+6281393504913",  // ❌ Confusing field name, phone number
  customer_id: 4,                    // Ticket customer ID
  // ❌ No user_id field
}
↓
Mobile App:
- Saves message with user_id = current_user.id (WRONG sender)
- Queries SQLite: user_name = NULL (user not synced)
- Displays: "You" or "Unknown" (WRONG attribution)
```

#### After Fix ✅
```
Backend Event (Admin Message):
{
  sender_name: "John Doe",  // ✅ Clear, semantic field name with sender's full name
  user_id: 5,               // ✅ Correct sender ID
  // customer_id omitted for admin messages
}
↓
Mobile App:
- Saves message with user_id = 5 (CORRECT sender from event)
- Queries SQLite: user_name may be NULL initially
- Falls back to sender_name from event: "John Doe" (CORRECT display)
- Message appears immediately with correct name ✓
```

---

## 🛠 Implementation Steps

### 1. Backend Changes

#### A. Update Socket.IO Service Event Emission

**File:** `backend/services/socketio_service.py`

**Changes:**
1. Rename parameter `customer_name` → `sender_name`
2. Use conditional payload for `user_id` vs `customer_id`

**Updated Code:**
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
    sender_name: str = None,  # ✅ Renamed from customer_name
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
        "sender_name": sender_name,  # ✅ Renamed field
    }

    # Conditional field based on sender type
    if sender_user_id:
        event_data["user_id"] = sender_user_id
    else:
        event_data["customer_id"] = customer_id

    # ... rest of emit logic
```

---

#### B. Update Messages Router Sender Name Logic

**File:** `backend/routers/messages.py`

**Changes:**
1. Rename variable `customer_name` → `sender_name`
2. Set sender name based on message source

**Updated Code:**
```python
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
    sender_name=sender_name,  # ✅ Renamed parameter
    sender_user_id=sender_id,
    customer_id=ticket.customer_id,
)
```

---

#### C. Update Backend Unit Tests

**File:** `backend/tests/test_socketio_service.py`

Add test cases to verify:
1. ✅ When `sender_user_id` is provided, `user_id` is included in event payload
2. ✅ When `sender_user_id` is None, `customer_id` is included instead
3. ✅ Both fields are never present simultaneously
4. ✅ Event data structure is correct for different message sources

**File:** `backend/tests/test_messages.py`

Add test cases to verify:
1. ✅ When admin creates a message, `sender_name` in WebSocket event contains user's full name
2. ✅ When customer message is received, `sender_name` contains customer's name/phone
3. ✅ WebSocket event is emitted with correct payload structure

---

### 2. Mobile App Changes

#### A. Update WebSocket Event Interface

**File:** `app/contexts/WebSocketContext.tsx`

**Changes:**
1. Rename field `customer_name` → `sender_name`
2. Add optional `user_id` field

**Updated Code:**
```typescript
export interface MessageCreatedEvent {
  ticket_id: number;
  message_id: number;
  phone_number: string;
  body: string;
  from_source: number;
  ts: string;
  ticket_number?: string;
  sender_name?: string;  // ✅ Renamed from customer_name
  user_id?: number;      // Present for admin/EO messages (from_source=2)
  customer_id?: number;  // Present for customer messages (from_source=1)
}
```

---

#### B. Update Chat WebSocket Hook

**File:** `app/hooks/chat/useChatWebSocket.ts` (lines 74-78)

**Current Code:**
```typescript
const savedMessage = daoManager.message.upsert(db, {
  id: event.message_id,
  from_source: event.from_source,
  message_sid: event.message_sid,
  customer_id: event.customer_id,
  user_id:
    event.from_source === MessageFrom.CUSTOMER ? null : userId || null,
  body: event.body,
  createdAt: event.ts,
});
```

**Updated Code:**
```typescript
const savedMessage = daoManager.message.upsert(db, {
  id: event.message_id,
  from_source: event.from_source,
  message_sid: event.message_sid,
  customer_id: event.customer_id || ticket.customer?.id, // Use event or fallback
  user_id: event.user_id || null, // Use user_id from event for admin messages
  body: event.body,
  createdAt: event.ts,
});
```

---

#### C. Update Message Display Logic

**File:** `app/hooks/chat/useTicketData.ts` (lines 11-34)

**Current Code:**
```typescript
const convertToUIMessage = (
  msg: MessageWithUsers,
  currentUserId?: number,
): Message => {
  const isCustomerMessage = msg.from_source === MessageFrom.CUSTOMER;
  const isLLMMessage = msg.from_source === MessageFrom.LLM;

  const userName = isCustomerMessage
    ? msg.customer_name
    : isLLMMessage
      ? "AI reply"
      : msg.user_id === currentUserId
        ? "You"
        : msg?.user_name || "You";

  return {
    id: msg.id,
    message_sid: msg.message_sid,
    name: userName,
    text: msg.body,
    sender: isCustomerMessage ? "customer" : "user",
    timestamp: msg.createdAt,
  };
};
```

**Updated Code:**
```typescript
const convertToUIMessage = (
  msg: MessageWithUsers,
  currentUserId?: number,
): Message => {
  const isCustomerMessage = msg.from_source === MessageFrom.CUSTOMER;
  const isLLMMessage = msg.from_source === MessageFrom.LLM;

  const userName = isCustomerMessage
    ? msg.customer_name
    : isLLMMessage
      ? "AI reply"
      : msg.user_id === currentUserId
        ? "You"
        : msg?.user_name || msg.customer_name || "Unknown User";

  return {
    id: msg.id,
    message_sid: msg.message_sid,
    name: userName,
    text: msg.body,
    sender: isCustomerMessage ? "customer" : "user",
    timestamp: msg.createdAt,
  };
};
```

**Note:** The mobile app's `MessageWithUsers` type uses `customer_name` field from database. No rename needed here since it's a database field name used by DAO layer.

---

## ✅ Expected Outcomes

1. **Immediate Display:** Admin/EO messages appear instantly in chat with correct sender names
2. **Proper Attribution:** No more "You" displayed for other users' messages
3. **No Bandwidth Increase:** Same payload size (conditional fields)
4. **Semantic Clarity:** Field names clearly indicate sender type (`user_id` vs `customer_id`)
5. **Graceful Degradation:** Falls back to `sender_name` from event when user record not synced locally
6. **Multi-User Support:** Different EOs on same ticket show correct sender names
7. **Semantic Field Names:** `sender_name` clearly indicates message sender regardless of type

---

## 🧪 Testing Checklist

### Backend Tests
- [ ] Verify event payload contains `user_id` for admin messages
- [ ] Verify event payload contains `customer_id` for customer messages
- [ ] Verify `sender_name` contains sender's full name for admin messages
- [ ] Verify `sender_name` contains customer name/phone for customer messages
- [ ] Verify `sender_name` contains "WHISPER" for LLM messages
- [ ] Run unit tests: `./dc.sh exec backend pytest tests/test_socketio_service.py -v`
- [ ] Run unit tests: `./dc.sh exec backend pytest tests/test_messages.py -v`
- [ ] Verify no regressions in existing tests

### Mobile App Tests
- [ ] Admin messages appear immediately with sender's name
- [ ] Customer messages still work correctly
- [ ] Multi-user scenarios: different EOs on same ticket show correct names
- [ ] Behavior when user not synced locally yet (fallback to sender_name from event)
- [ ] WebSocket reconnection scenarios
- [ ] Message ordering preserved
- [ ] No duplicate messages

### Integration Tests
- [ ] End-to-end: Admin sends message → appears on other EO's device instantly
- [ ] End-to-end: Customer sends message → appears on EO's device instantly
- [ ] Multiple admins on same ticket can see each other's messages with correct names
- [ ] Push notifications still work correctly

---

## 📁 Related Files

### Backend
- `backend/services/socketio_service.py` - WebSocket event emission
- `backend/routers/messages.py` - Message creation endpoint
- `backend/routers/whatsapp.py` - WhatsApp webhook (customer messages)
- `backend/tests/test_socketio_service.py` - Socket.IO service tests
- `backend/tests/test_messages.py` - Messages endpoint tests

### Mobile App
- `app/contexts/WebSocketContext.tsx` - WebSocket event types and listeners
- `app/hooks/chat/useChatWebSocket.ts` - Real-time message handling
- `app/hooks/chat/useTicketData.ts` - Message display logic
- `app/database/dao/types/message.ts` - Message type definitions
- `app/components/chat/message-bubble.tsx` - Message UI component

---

## ⏱ Timeline

**Estimated implementation time:** 2-3 hours

- Backend changes: 30 minutes
- Backend tests: 45 minutes
- Mobile app changes: 45 minutes
- Testing: 30 minutes

---

## 📝 Notes

- This fix addresses the immediate display issue without requiring full user synchronization
- The conditional payload approach maintains backward compatibility while improving clarity
- Semantic field names (`user_id` vs `customer_id`) make the code more maintainable
- Graceful degradation ensures messages display even when user records aren't synced locally
- Future enhancement: Consider syncing user records to mobile app for richer user information display

---

## 🔄 Rollback Plan

If issues arise after deployment:

1. **Backend:** Revert changes to `socketio_service.py` and `messages.py`
2. **Mobile App:** Revert changes to WebSocket interfaces and handlers
3. **Database:** No schema changes required, so no database rollback needed
4. **Tests:** Keep new tests but mark as expected failures until re-implementation

**Risk Level:** Low (changes are additive and don't break existing functionality)
