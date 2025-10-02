// EO Users table migration
export const usersMigration = `
-- EO Users table migration
-- This table stores user data
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    fullName TEXT NOT NULL,
    phoneNumber TEXT UNIQUE NOT NULL,
    userType TEXT NOT NULL DEFAULT 'eo',
    isActive BOOLEAN NOT NULL DEFAULT 1,
    invitationStatus TEXT NULL,
    password_set_at TEXT NULL,
    administrativeLocation TEXT NULL,
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),
    updatedAt TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Create indexes for better query performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phoneNumber ON users(phoneNumber);
CREATE INDEX idx_users_userType ON users(userType);
CREATE INDEX idx_users_isActive ON users(isActive);
`;
