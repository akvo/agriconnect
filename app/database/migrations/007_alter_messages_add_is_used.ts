// Add is_used column to messages table
// This tracks whether a WHISPER message has been used/accepted by the user
export const alterMessagesAddIsUsedMigration = `
-- Add is_used column to messages table
-- 0 = not used (default), 1 = used
ALTER TABLE messages ADD COLUMN is_used INTEGER NOT NULL DEFAULT 0;

-- Create index for better query performance on WHISPER messages
CREATE INDEX idx_messages_is_used ON messages(is_used);
`;
