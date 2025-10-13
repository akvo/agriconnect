// Alter from_source and user_id columns in messages table AND add status column
// Changes from_source from TEXT to INTEGER to match backend MessageFrom
// Changes user_id to allow NULL values for customer messages
// Changes message_type from TEXT to INTEGER
// Adds status column (1=PENDING, 2=REPLIED, 3=RESOLVED)
export const alterMessagesAddStatusMigration = `
-- SQLite doesn't support ALTER COLUMN directly, so we need to:
-- 1. Create new table with correct schema (including status column)
-- 2. Copy data from old table
-- 3. Drop old table
-- 4. Rename new table

-- Step 1: Create new messages table with correct types and status column
CREATE TABLE messages_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_source INTEGER NOT NULL, -- Message source: 1=CUSTOMER, 2=USER, 3=LLM (matches backend MessageFrom)
    message_sid TEXT UNIQUE NOT NULL, -- WhatsApp message SID or unique identifier
    customer_id INTEGER NOT NULL, -- Reference to customer_users.id
    user_id INTEGER, -- Reference to users.id (NULL for customer messages)
    body TEXT NOT NULL, -- Message content
    message_type INTEGER, -- Message type: 1=REPLY, 2=WHISPER (matches backend MessageType)
    status INTEGER NOT NULL DEFAULT 1, -- Message status: 1=PENDING, 2=REPLIED, 3=RESOLVED
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),

    -- Foreign key constraints
    FOREIGN KEY (customer_id) REFERENCES customer_users(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Step 2: Copy data from old table to new table
-- Convert from_source: assume existing data is from USER (2) if user_id is set, otherwise CUSTOMER (1)
-- Convert message_type from TEXT to INTEGER
-- Set default status to PENDING (1)
INSERT INTO messages_new (id, from_source, message_sid, customer_id, user_id, body, message_type, status, createdAt)
SELECT
    id,
    CASE
        WHEN user_id IS NOT NULL THEN 2  -- USER
        ELSE 1  -- CUSTOMER
    END as from_source,
    message_sid,
    customer_id,
    user_id,
    body,
    CASE message_type
        WHEN 'reply' THEN 1  -- REPLY
        WHEN 'whisper' THEN 2  -- WHISPER
        ELSE NULL
    END as message_type,
    1 as status,  -- Default to PENDING
    createdAt
FROM messages;

-- Step 3: Drop old table
DROP TABLE messages;

-- Step 4: Rename new table
ALTER TABLE messages_new RENAME TO messages;

-- Step 5: Recreate indexes
CREATE INDEX idx_messages_customer_id ON messages(customer_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_message_sid ON messages(message_sid);
CREATE INDEX idx_messages_from_source ON messages(from_source);
CREATE INDEX idx_messages_message_type ON messages(message_type);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_createdAt ON messages(createdAt);
`;
