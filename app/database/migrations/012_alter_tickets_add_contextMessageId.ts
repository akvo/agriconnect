// Alter tickets table to add contextMessageId column
// This stores the original customer question for better ticket context
export const alterTicketsAddContextMessageIdMigration = `
-- Add contextMessageId column to tickets table
-- This is a nullable foreign key to messages table

-- Step 1: Create new tickets table with contextMessageId
CREATE TABLE tickets_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticketNumber TEXT UNIQUE NOT NULL,
    customerId INTEGER NOT NULL,
    messageId INTEGER NOT NULL,
    contextMessageId INTEGER NULL,
    lastMessageId INTEGER NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    unreadCount INTEGER NOT NULL DEFAULT 0,
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),
    updatedAt TEXT NOT NULL DEFAULT (datetime('now')),
    resolvedAt TEXT NULL,
    resolvedBy INTEGER NULL,
    FOREIGN KEY (customerId) REFERENCES customer_users(id) ON DELETE CASCADE,
    FOREIGN KEY (messageId) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (contextMessageId) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (lastMessageId) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (resolvedBy) REFERENCES users(id) ON DELETE SET NULL
);

-- Step 2: Copy data from old table to new table
INSERT INTO tickets_new (
    id, ticketNumber, customerId, messageId, contextMessageId, lastMessageId,
    status, unreadCount, createdAt, updatedAt, resolvedAt, resolvedBy
)
SELECT
    id, ticketNumber, customerId, messageId, NULL as contextMessageId, lastMessageId,
    status, unreadCount, createdAt, updatedAt, resolvedAt, resolvedBy
FROM tickets;

-- Step 3: Drop old table
DROP TABLE tickets;

-- Step 4: Rename new table
ALTER TABLE tickets_new RENAME TO tickets;

-- Step 5: Recreate indexes for better query performance
CREATE INDEX idx_tickets_customerId ON tickets(customerId);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_ticketNumber ON tickets(ticketNumber);
CREATE INDEX idx_tickets_lastMessageId ON tickets(lastMessageId);
CREATE INDEX idx_tickets_contextMessageId ON tickets(contextMessageId);
`;
