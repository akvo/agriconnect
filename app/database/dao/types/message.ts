// Message types and interfaces
// Note: from_source uses MessageFrom constants (1=CUSTOMER, 2=USER, 3=LLM)
// Note: status uses MessageStatus constants (1=PENDING, 2=REPLIED, 3=RESOLVED)
// Note: message_type (1=REPLY, 2=WHISPER)
// Note: is_used (0=not used, 1=used) - tracks if WHISPER message has been accepted
// Note: delivery_status - Twilio delivery tracking: PENDING, QUEUED, SENDING, SENT, DELIVERED, READ, FAILED, UNDELIVERED
// Import from @/constants/messageSource and @/constants/messageStatus when needed
export interface Message {
  id: number;
  from_source: number; // 1=CUSTOMER, 2=USER, 3=LLM
  message_sid: string;
  customer_id: number;
  user_id: number | null;
  body: string;
  message_type: number;
  status: number; // 1=PENDING, 2=REPLIED, 3=RESOLVED
  is_used: number; // 0=not used, 1=used (for WHISPER messages)
  delivery_status: string; // Twilio delivery status: PENDING, QUEUED, SENDING, SENT, DELIVERED, READ, FAILED, UNDELIVERED
  createdAt: string;
  updatedAt: string;
}

export interface CreateMessageData {
  from_source: number; // Use MessageFrom constants
  message_sid: string;
  customer_id: number;
  user_id: number | null;
  body: string;
  createdAt: string;
  message_type?: number;
  status?: number; // Use MessageStatus constants (default: PENDING=1)
  is_used?: number; // 0=not used, 1=used (default: 0)
  delivery_status?: string; // Twilio delivery status (default: PENDING)
}

export interface UpdateMessageData {
  from_source?: number;
  message_sid?: string;
  customer_id?: number;
  user_id?: number | null;
  body?: string;
  message_type?: number;
  status?: number; // Use MessageStatus constants
  is_used?: number; // 0=not used, 1=used
  delivery_status?: string; // Twilio delivery status
}

// Extended message interface with user details (for inbox/conversation views)
export interface MessageWithUsers extends Message {
  customer_name: string;
  customer_phone: string;
  user_name: string | null; // Full name of user who sent the message (for USER messages)
  user_email: string | null; // Email of user who sent the message (for USER messages)
}

// Conversation summary for inbox
export interface ConversationSummary {
  customer_id: number;
  user_id: number;
  customer_name: string;
  customer_phone: string;
  user_name: string;
  user_email: string;
  last_message: string;
  last_message_type: string;
  last_message_time: string;
  unread_count: number;
}
