/**
 * Message Status Constants
 * Matches backend MessageStatus enum values
 * Backend: backend/models/message.py
 */

export const MessageStatus = {
  PENDING: 1, // Message created, not yet replied
  REPLIED: 2, // EO has sent a reply
  RESOLVED: 3, // Ticket/message marked as resolved
} as const;

export type MessageStatusType =
  (typeof MessageStatus)[keyof typeof MessageStatus];

/**
 * Convert status integer to human-readable string
 */
export const getStatusLabel = (status: number): string => {
  switch (status) {
    case MessageStatus.PENDING:
      return "Pending";
    case MessageStatus.REPLIED:
      return "Replied";
    case MessageStatus.RESOLVED:
      return "Resolved";
    default:
      return "Unknown";
  }
};
