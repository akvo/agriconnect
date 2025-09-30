// Customer Users table migration
export const customerUsersMigration = `
-- Customer Users table migration
-- This table stores customer customer data
CREATE TABLE customer_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Create indexes for better query performance
CREATE INDEX idx_customer_users_phone_number ON customer_users(phone_number);
CREATE INDEX idx_customer_users_language ON customer_users(language);
`;
