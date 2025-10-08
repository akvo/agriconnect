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
  lastMessage?: { content: string; timestamp: string };
  resolvedAt?: string | null;
  respondedBy?: User;
  updatedAt?: string | null;
};

export interface CreateTicketData {
  id?: number;
  customerId: number;
  messageId: number;
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
}
