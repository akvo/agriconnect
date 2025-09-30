// Messages table migration
export const messagesMigration = `
-- Messages table migration
-- This table stores chat/message data between customers and EOs
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_source TEXT NOT NULL, -- Source identifier (phone number or system ID)
    message_sid TEXT UNIQUE NOT NULL, -- WhatsApp message SID or unique identifier
    customer_id INTEGER NOT NULL, -- Reference to customer_users.id
    eo_id INTEGER NOT NULL, -- Reference to eo_users.id
    body TEXT NOT NULL, -- Message content
    message_type TEXT NOT NULL DEFAULT 'text', -- text, image, audio, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Foreign key constraints
    FOREIGN KEY (customer_id) REFERENCES customer_users(id) ON DELETE CASCADE,
    FOREIGN KEY (eo_id) REFERENCES eo_users(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX idx_messages_customer_id ON messages(customer_id);
CREATE INDEX idx_messages_eo_id ON messages(eo_id);
CREATE INDEX idx_messages_message_sid ON messages(message_sid);
CREATE INDEX idx_messages_from_source ON messages(from_source);
CREATE INDEX idx_messages_message_type ON messages(message_type);
CREATE INDEX idx_messages_created_at ON messages(created_at);
`;
