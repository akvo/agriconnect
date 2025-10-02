// Messages table migration
export const messagesMigration = `
-- Messages table migration
-- This table stores chat/message data between customers and EOs
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_source TEXT NOT NULL, -- Source identifier (phone number or system ID)
    message_sid TEXT UNIQUE NOT NULL, -- WhatsApp message SID or unique identifier
    customer_id INTEGER NOT NULL, -- Reference to customer_users.id
    user_id INTEGER NOT NULL, -- Reference to users.id
    body TEXT NOT NULL, -- Message content
    message_type TEXT NOT NULL DEFAULT 'text', -- text, image, audio, etc.
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Foreign key constraints
    FOREIGN KEY (customer_id) REFERENCES customer_users(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX idx_messages_customer_id ON messages(customer_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_message_sid ON messages(message_sid);
CREATE INDEX idx_messages_from_source ON messages(from_source);
CREATE INDEX idx_messages_message_type ON messages(message_type);
CREATE INDEX idx_messages_createdAt ON messages(createdAt);
`;
