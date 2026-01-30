type Customer = {
  id: number;
  name?: string;
  phoneNumber: string;
  language?: string;
} | null;
type User = { id: number; name: string } | null;
type Message = { id: number; body: string; timestamp: string } | null;

export type Ticket = {
  id: number;
  customer: Customer;
  message: Message;
  contextMessage?: Message;
  status: string;
  createdAt: string;
  resolver: User;
  ticketNumber: string;
  unreadCount?: number;
  lastMessage?: { body: string; timestamp: string };
  lastMessageId?: number | null;
  resolvedAt?: string | null;
  respondedBy?: User;
  updatedAt?: string | null;
};

export interface CreateTicketData {
  id?: number;
  customerId: number;
  messageId: number;
  contextMessageId?: number | null;
  status: string;
  ticketNumber: string;
  unreadCount?: number;
  resolvedAt?: string | null;
  resolvedBy?: number | null;
}

export interface UpdateTicketData {
  status?: string;
  resolvedAt?: string | null;
  resolvedBy?: number | null;
  unreadCount?: number;
  lastMessageId?: number | null;
  contextMessageId?: number | null;
}
