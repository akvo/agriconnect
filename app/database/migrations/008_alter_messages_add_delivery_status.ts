// Alter messages table to add delivery_status column
// This column tracks Twilio delivery status: PENDING, QUEUED, SENDING, SENT, DELIVERED, READ, FAILED, UNDELIVERED
// Used to filter out failed messages from the chat UI
export const alterMessagesAddDeliveryStatusMigration = `
-- Add delivery_status column to messages table
-- Default to 'PENDING' for existing messages
-- This matches backend DeliveryStatus enum
ALTER TABLE messages ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'PENDING';

-- Create index for delivery_status for efficient filtering
CREATE INDEX idx_messages_delivery_status ON messages(delivery_status);
`;
