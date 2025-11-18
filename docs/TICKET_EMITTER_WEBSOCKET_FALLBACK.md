# TicketEmitter as WebSocket Fallback Implementation

**Date:** 2025-11-18
**Status:** Implemented
**Related Files:**
- `app/contexts/NotificationContext.tsx`
- `app/app/(tabs)/inbox.tsx`
- `app/app/chat/[ticketId].tsx`
- `app/utils/ticketEvents.ts`
- `app/hooks/chat/useChatWebSocket.ts`

---

## Problem Statement

The WebSocket connection on the mobile app is unstable, and there's a possibility that new messages or tickets don't appear instantly on the inbox/chat screens when WebSocket is disconnected or experiencing issues.

### Observed Issues
1. WebSocket disconnections prevent real-time updates
2. Push notifications arrive reliably, but weren't being used to update UI
3. Users had to manually refresh to see new messages/tickets

---

## Solution: Dual Event System

Implement a **dual event system** where both WebSocket AND push notification events can update the UI, with proper deduplication to prevent duplicates.

### Event Sources
1. **WebSocket Events** (Primary) - Real-time socket.io events from backend
2. **TicketEmitter Events** (Fallback) - Local EventEmitter triggered by push notifications

### Event Flow

```
Backend Event (message_created)
    ├─> WebSocket → emit_message_received() → socket.io → onMessageCreated()
    └─> Push Notification → NotificationContext → ticketEmitter.emit()

Both trigger the same handler logic with deduplication
```

---

## Architecture

### Current Implementation

**NotificationContext.tsx (Lines 189-198)**
```typescript
notificationListener.current =
  Notifications.addNotificationReceivedListener((notification) => {
    console.log("Notification received:", notification);
    setNotification(notification);
    const notificationData = notification?.request?.content?.data;
    ticketEmitter.emit(MESSAGE_CREATED, {
      ...notificationData,
      body: notification.request.content.body,
    });
  });
```

**Key Insight:** Push notifications ALREADY emit `MESSAGE_CREATED` events via `ticketEmitter`, but components weren't listening properly.

---

## Implementation Plan: Option 1 (Unified Event Handler)

### Strategy
Create a **unified event handler** that both WebSocket `onMessageCreated()` and `ticketEmitter` can call, ensuring:
- No code duplication
- Consistent behavior across event sources
- Built-in deduplication

### Changes Required

#### 1. **inbox.tsx** - Implement Functional TicketEmitter Listener

**Current Code (Lines 190-199):**
```typescript
// Subscribe to real-time events
useEffect(() => {
  ticketEmitter.on(MESSAGE_CREATED, (data) => {
    console.log("Real-time message created event received:", data);
  });

  return () => {
    ticketEmitter.off(MESSAGE_CREATED);
  };
}, []);
```

**Problem:** Only logs the event, doesn't update UI.

**Solution:** Convert the push notification data to `MessageCreatedEvent` format and call the same handler.

**New Implementation:**
```typescript
// Subscribe to ticketEmitter (fallback for push notifications)
useEffect(() => {
  const handleTicketEmitterMessage = (data: any) => {
    console.log("[Inbox] ticketEmitter MESSAGE_CREATED received:", data);

    // Convert push notification data to MessageCreatedEvent format
    const event: MessageCreatedEvent = {
      ticket_id: parseInt(data.ticketId),
      message_id: parseInt(data.messageId),
      phone_number: data.phone_number || "",
      body: data.body || "",
      from_source: 1, // CUSTOMER
      ts: new Date().toISOString(),
      ticket_number: data.ticketNumber,
      sender_name: data.name,
      customer_id: data.customer_id,
      customer_name: data.name,
    };

    // Call the same handler as WebSocket (will be extracted)
    handleMessageCreated(event);
  };

  ticketEmitter.on(MESSAGE_CREATED, handleTicketEmitterMessage);

  return () => {
    ticketEmitter.off(MESSAGE_CREATED, handleTicketEmitterMessage);
  };
}, [/* dependencies */]);
```

**Deduplication:** Already implemented (inbox.tsx:272-277) - checks if ticket exists before creating optimistic ticket.

#### 2. **[ticketId].tsx** - Implement Functional TicketEmitter Listener

**Current Code (Lines 130-138):**
```typescript
// Handle ticketEmitter
useEffect(() => {
  ticketEmitter.addListener(MESSAGE_CREATED, (data) => {
    console.log("[ChatScreen] MESSAGE_CREATED event received", data);
  });

  return () => {
    ticketEmitter.off(MESSAGE_CREATED);
  };
}, []);
```

**Problem:** Only logs the event, doesn't update messages list.

**Solution:** Convert push notification data to `MessageCreatedEvent` format and reuse the same handler from `useChatWebSocket`.

**Approach:** Extract the message handling logic from `useChatWebSocket.ts` into a standalone function that can be called by both WebSocket and ticketEmitter.

**New Implementation:**
```typescript
// Handle ticketEmitter (fallback for push notifications)
useEffect(() => {
  const handleTicketEmitterMessage = async (data: any) => {
    console.log("[ChatScreen] ticketEmitter MESSAGE_CREATED received:", data);

    // Only process if this is the current ticket
    if (parseInt(data.ticketId) !== ticket?.id) {
      return;
    }

    // Convert push notification data to MessageCreatedEvent format
    const event: MessageCreatedEvent = {
      ticket_id: parseInt(data.ticketId),
      message_id: parseInt(data.messageId),
      phone_number: data.phone_number || "",
      body: data.body || "",
      from_source: 1, // CUSTOMER
      ts: new Date().toISOString(),
      ticket_number: data.ticketNumber,
      sender_name: data.name,
      customer_id: data.customer_id,
      customer_name: data.name,
    };

    // Call the same message handler (will be extracted from useChatWebSocket)
    await handleMessageCreated(event);
  };

  ticketEmitter.on(MESSAGE_CREATED, handleTicketEmitterMessage);

  return () => {
    ticketEmitter.off(MESSAGE_CREATED, handleTicketEmitterMessage);
  };
}, [ticket?.id /* other dependencies */]);
```

**Deduplication:** Already implemented in `useChatWebSocket.ts:112-137` - checks if message exists before adding.

#### 3. **Extract Shared Handler Logic** (Optional Enhancement)

Create a reusable message handler that both WebSocket and ticketEmitter can call:

**useChatWebSocket.ts Enhancement:**
```typescript
// Extract message handling into standalone function
const handleMessageCreatedEvent = async (event: MessageCreatedEvent) => {
  if (!ticket?.id || event.ticket_id !== ticket?.id) {
    return;
  }

  console.log("[Chat] Received new message:", event);

  try {
    if (event.from_source === MessageFrom.CUSTOMER) {
      console.log("[Chat] Customer message, waiting for AI suggestion...");
      setAISuggestionLoading(true);
      setAISuggestionUsed(false);
      setAISuggestion(null);
    }

    // Save message to SQLite
    const savedMessage = daoManager.message.upsert(db, {
      id: event.message_id,
      from_source: event.from_source,
      message_sid: `MSG_${Date.now()}`,
      customer_id: event.customer_id || ticket.customer?.id,
      user_id: event.user_id || null,
      body: event.body,
      createdAt: event.ts,
    });

    if (savedMessage) {
      const dbMessage = daoManager.message.findByIdWithUsers(db, savedMessage.id);

      // Update last message info
      updateTicket(ticket.id!, {
        lastMessageId: event.message_id,
        unreadCount: 0,
      });
      await daoManager.ticket.update(db, ticket.id, {
        lastMessageId: event.message_id,
        unreadCount: 0,
      });

      if (dbMessage) {
        const uiMessage = convertToUIMessage(dbMessage, userId);

        setMessages((prev: Message[]) => {
          // Deduplication check
          const existingIndex = prev.findIndex(
            (m) => m.id === uiMessage.id || m.message_sid === uiMessage.message_sid
          );

          if (existingIndex !== -1) {
            const existing = prev[existingIndex];
            if (existing.id !== uiMessage.id && existing.message_sid === uiMessage.message_sid) {
              console.log(`[Chat] Replacing optimistic message`);
              const updated = [...prev];
              updated[existingIndex] = uiMessage;
              return updated;
            }
            console.log(`[Chat] Message already exists, skipping`);
            return prev;
          }

          console.log(`[Chat] Adding new message ${uiMessage.id}`);
          return [...prev, uiMessage];
        });

        setTimeout(() => scrollToBottom(true), 200);
      }
    }
  } catch (error) {
    console.error("[Chat] Error handling new message:", error);
  }
};

// Then use it in both WebSocket and ticketEmitter listeners
```

---

## Deduplication Strategy

### inbox.tsx Deduplication

**For Existing Tickets (Lines 195-227):**
```typescript
const ticketIndex = tickets.findIndex((t: Ticket) => t.id === event.ticket_id);

if (ticketIndex !== -1) {
  setTickets((prevTickets: Ticket[]) => {
    const ticket = prevTickets[ticketIndex];

    // CRITICAL: Check if message already processed (prevent duplicate unread count increments)
    if (ticket.lastMessageId === event.message_id) {
      console.log(`[Inbox] Message already processed, skipping duplicate`);
      return prevTickets;
    }

    const newUnreadCount = (ticket.unreadCount || 0) + 1;

    return prevTickets.map((t: Ticket) =>
      t.id === event.ticket_id
        ? { ...t, unreadCount: newUnreadCount, lastMessageId: event.message_id, lastMessage: {...}, updatedAt: event.ts }
        : t
    );
  });
}
```

**For New Tickets (Lines 264-308):**
```typescript
setTickets((prevTickets: Ticket[]) => {
  // CRITICAL: Check if ticket already exists (prevents duplicates)
  const alreadyExists = prevTickets.some((t: Ticket) => t.id === event.ticket_id);
  if (alreadyExists) {
    console.log("[Inbox] Ticket already exists, skipping duplicate");
    return prevTickets;
  }

  // Create optimistic ticket
  return [{ id: event.ticket_id, ... }, ...prevTickets];
});
```

### [ticketId].tsx Deduplication

**In useChatWebSocket.ts (Lines 112-137):**
```typescript
setMessages((prev: Message[]) => {
  const existingIndex = prev.findIndex(
    (m) => m.id === uiMessage.id || m.message_sid === uiMessage.message_sid
  );

  if (existingIndex !== -1) {
    // Message already exists
    if (existing.id !== uiMessage.id && existing.message_sid === uiMessage.message_sid) {
      // Replace optimistic message with backend version
      console.log(`[Chat] Replacing optimistic message`);
      const updated = [...prev];
      updated[existingIndex] = uiMessage;
      return updated;
    }

    console.log(`[Chat] Message already exists, skipping`);
    return prev;
  }

  // Add new message
  console.log(`[Chat] Adding new message ${uiMessage.id}`);
  return [...prev, uiMessage];
});
```

---

## Event Data Format Mapping

### Push Notification Data (from NotificationContext)
```typescript
{
  type: "message_created",
  ticketNumber: "20251117222304",
  ticketId: "9",
  name: "+6281542751677",
  messageId: "148",
  body: "How is cassava propagated by farmers?"  // from notification.request.content.body
}
```

### MessageCreatedEvent (WebSocket format)
```typescript
{
  ticket_id: number,
  message_id: number,
  phone_number: string,
  body: string,
  from_source: number,
  ts: string,
  ticket_number?: string,
  sender_name?: string,
  customer_id?: number,
  customer_name?: string
}
```

### Conversion Logic
```typescript
const event: MessageCreatedEvent = {
  ticket_id: parseInt(data.ticketId),           // "9" → 9
  message_id: parseInt(data.messageId),         // "148" → 148
  phone_number: data.phone_number || "",        // May not be in push data
  body: data.body || "",                        // From notification body
  from_source: 1,                               // CUSTOMER (always 1 for push notifications)
  ts: new Date().toISOString(),                 // Current timestamp
  ticket_number: data.ticketNumber,             // "20251117222304"
  sender_name: data.name,                       // "+6281542751677"
  customer_id: data.customer_id,                // May be in data
  customer_name: data.name,                     // Same as sender_name
};
```

---

## Benefits

1. ✅ **Reliability:** Push notifications provide fallback when WebSocket fails
2. ✅ **No Duplicates:** Built-in deduplication prevents double-updates
3. ✅ **Consistency:** Same handler logic for both event sources
4. ✅ **Minimal Changes:** Reuses existing WebSocket handler logic
5. ✅ **Already Prepared:** Duplicate check already implemented in inbox.tsx
6. ✅ **User Experience:** Messages appear instantly even without WebSocket

---

## Testing Scenarios

### Scenario 1: WebSocket Disconnected
1. Disconnect WebSocket (airplane mode → back online without WS reconnect)
2. Send message from another device
3. **Expected:** Push notification arrives → ticketEmitter updates UI
4. **Verify:** Message appears in inbox/chat without manual refresh

### Scenario 2: Both WebSocket and Push Notification
1. Keep WebSocket connected
2. Send message
3. **Expected:** Both WebSocket AND push notification fire
4. **Verify:** Only one message appears (deduplication works)
5. **Log Check:** Should see "[Inbox] Ticket already exists, skipping duplicate" OR "[Chat] Message already exists, skipping"

### Scenario 3: New Ticket Creation
1. Disconnect WebSocket
2. Create new ticket (escalate from WhatsApp)
3. **Expected:** Push notification creates optimistic ticket
4. **Verify:** New ticket appears in inbox instantly

### Scenario 4: Race Condition
1. WebSocket AND push notification arrive simultaneously
2. **Expected:** First one to process creates/updates ticket/message
3. **Verify:** Second one is skipped by deduplication check
4. **No errors or duplicate entries**

---

## Implementation Checklist

- [x] Update `inbox.tsx` to handle ticketEmitter events functionally
- [x] Update `[ticketId].tsx` to handle ticketEmitter events functionally
- [ ] Test WebSocket disconnected scenario
- [ ] Test dual event scenario (both fire)
- [ ] Test new ticket creation via push notification
- [ ] Test message updates via push notification
- [ ] Verify no duplicate tickets/messages appear
- [ ] Check logs for deduplication messages
- [ ] Test on physical device (push notifications don't work in simulator)

---

## Notes

- Push notifications only work on **physical devices** (not Expo Go or simulators)
- The `ticketEmitter` is already emitting events from `NotificationContext.tsx:195`
- Deduplication logic was already implemented in the previous fix (inbox.tsx:272-277)
- WebSocket remains the primary real-time mechanism; ticketEmitter is the fallback

---

## Future Enhancements

1. **Retry Logic:** If ticketEmitter update fails, retry with exponential backoff
2. **Conflict Resolution:** Handle cases where WebSocket and push notification have different data
3. **Analytics:** Track which event source successfully updated the UI
4. **Offline Queue:** Queue ticketEmitter events when app is backgrounded

---

## Related Documentation

- `PUSH_NOTIFICATIONS.md` - Push notification setup and configuration
- `WEBSOCKET_MULTI_DEVICE_TOKEN_REFRESH_FIX.md` - WebSocket connection management
