// Ticket table migration
/**
 * id
 * ticketNumber (unique)
 * customerId (FK)
 * messageId (FK)
 * status ENUM('pending','replied','resolved') DEFAULT 'pending'
 * lastMessageAt
 * unreadCount
 * createdAt
 * updatedAt
 * resolvedAt (nullable)
 * resolvedBy (FK to users, nullable)
 *
 * Indexes on (resolvedAt, lastMessageAt DESC) and (customerId) for fast queries.
 *
 */
export const ticketMigration = `
-- Ticket table migration
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticketNumber TEXT UNIQUE NOT NULL,
    customerId INTEGER NOT NULL,
    messageId INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    lastMessageAt TEXT NOT NULL DEFAULT (datetime('now')),
    unreadCount INTEGER NOT NULL DEFAULT 0,
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),
    updatedAt TEXT NOT NULL DEFAULT (datetime('now')),
    resolvedAt TEXT NULL,
    resolvedBy INTEGER NULL,
    FOREIGN KEY (customerId) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (messageId) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (resolvedBy) REFERENCES users(id) ON DELETE SET NULL
);

-- Create indexes for better query performance
CREATE INDEX idx_tickets_resolvedAt_lastMessageAt ON tickets(resolvedAt, lastMessageAt DESC);
CREATE INDEX idx_tickets_customerId ON tickets(customerId);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_ticketNumber ON tickets(ticketNumber);
`;
