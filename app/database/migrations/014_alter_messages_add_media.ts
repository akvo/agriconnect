// Alter messages table to add media_url and media_type columns
// media_url: URL to media file (images, voice messages, etc.)
// media_type: Type of media - TEXT, VOICE, IMAGE, VIDEO, DOCUMENT, LOCATION, OTHER
export const alterMessagesAddMediaMigration = `
-- Add media_url column to messages table
-- Stores relative URL path to media files (e.g., /media/abc123.jpg)
ALTER TABLE messages ADD COLUMN media_url TEXT DEFAULT NULL;

-- Add media_type column to messages table
-- Default to 'TEXT' for existing and text-only messages
-- This matches backend MediaType enum
ALTER TABLE messages ADD COLUMN media_type TEXT NOT NULL DEFAULT 'TEXT';

-- Create index for media_type for efficient filtering
CREATE INDEX idx_messages_media_type ON messages(media_type);
`;
