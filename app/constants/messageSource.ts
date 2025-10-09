/**
 * Message Source Constants
 * These constants must match the backend MessageFrom class
 * backend/models/message.py
 */

export const MessageFrom = {
  CUSTOMER: 1,
  USER: 2,
  LLM: 3,
} as const;

export type MessageFromType = (typeof MessageFrom)[keyof typeof MessageFrom];

/**
 * Convert MessageFrom integer to string representation
 */
export function messageFromToString(from: number): string {
  switch (from) {
    case MessageFrom.CUSTOMER:
      return "whatsapp";
    case MessageFrom.USER:
      return "system";
    case MessageFrom.LLM:
      return "llm";
    default:
      return "unknown";
  }
}

/**
 * Convert string representation to MessageFrom integer
 */
export function stringToMessageFrom(from: string): number {
  switch (from.toLowerCase()) {
    case "whatsapp":
    case "customer":
      return MessageFrom.CUSTOMER;
    case "system":
    case "user":
      return MessageFrom.USER;
    case "llm":
      return MessageFrom.LLM;
    default:
      return MessageFrom.CUSTOMER; // Default to customer
  }
}
