// Message types and interfaces
export interface Message {
  id: number;
  from_source: string;
  message_sid: string;
  customer_id: number;
  user_id: number;
  body: string;
  message_type: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateMessageData {
  from_source: string;
  message_sid: string;
  customer_id: number;
  user_id: number;
  body: string;
  message_type?: string;
}

export interface UpdateMessageData {
  from_source?: string;
  message_sid?: string;
  customer_id?: number;
  user_id?: number;
  body?: string;
  message_type?: string;
}

// Extended message interface with user details (for inbox/conversation views)
export interface MessageWithUsers extends Message {
  customer_name: string;
  customer_phone: string;
  eo_name: string;
  eo_email: string;
}

// Conversation summary for inbox
export interface ConversationSummary {
  customer_id: number;
  user_id: number;
  customer_name: string;
  customer_phone: string;
  eo_name: string;
  eo_email: string;
  last_message: string;
  last_message_type: string;
  last_message_time: string;
  unread_count: number;
}
