// Customer Users table migration
export const customerUsersMigration = `
-- Customer Users table migration
-- This table stores customer customer data
CREATE TABLE customer_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phoneNumber TEXT UNIQUE NOT NULL,
    fullName TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),
    updatedAt TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Create indexes for better query performance
CREATE INDEX idx_customer_users_phoneNumber ON customer_users(phoneNumber);
CREATE INDEX idx_customer_users_language ON customer_users(language);
`;
