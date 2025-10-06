type Customer = { id: number; name: string };
type User = { id: number; name: string } | null;
type Message = { id: number; body: string; timestamp: string } | null;

export type Ticket = {
  id: number;
  customer: Customer;
  message: Message;
  status: string;
  createdAt: string;
  resolver: User;
  ticketNumber: string;
  unreadCount?: number;
  lastMessageAt?: string;
  lastMessage?: { content: string; timestamp: string };
  resolvedAt?: string | null;
  respondedBy?: User;
};

export interface CreateTicketData {
  customerId: number;
  messageId: number;
  status: string;
  ticketNumber: string;
  unreadCount?: number;
  lastMessageAt?: string;
}

export interface UpdateTicketData {
  status?: string;
  resolvedAt?: string | null;
  resolvedBy?: number | null;
  unreadCount?: number;
  lastMessageAt?: string;
  respondedById?: number | null;
}
