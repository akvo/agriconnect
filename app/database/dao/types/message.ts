// Message types and interfaces
// Note: from_source uses MessageFrom constants (1=CUSTOMER, 2=USER, 3=LLM)
// Import from @/constants/messageSource when needed
export interface Message {
  id: number;
  from_source: number; // 1=CUSTOMER, 2=USER, 3=LLM
  message_sid: string;
  customer_id: number;
  user_id: number | null;
  body: string;
  message_type: string;
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
  message_type?: string;
}

export interface UpdateMessageData {
  from_source?: number;
  message_sid?: string;
  customer_id?: number;
  user_id?: number | null;
  body?: string;
  message_type?: string;
}

// Extended message interface with user details (for inbox/conversation views)
export interface MessageWithUsers extends Message {
  customer_name: string;
  customer_phone: string;
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
