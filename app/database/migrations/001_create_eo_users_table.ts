// EO Users table migration
export const eoUsersMigration = `
-- EO Users table migration
-- This table stores Extension Officers (EO) user data
CREATE TABLE eo_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    phone_number TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    user_type TEXT NOT NULL DEFAULT 'eo',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    invitation_status TEXT NULL,
    password_set_at TEXT NULL,
    administrative_location TEXT NULL,
    authToken TEXT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Create indexes for better query performance
CREATE INDEX idx_eo_users_email ON eo_users(email);
CREATE INDEX idx_eo_users_phone_number ON eo_users(phone_number);
CREATE INDEX idx_eo_users_user_type ON eo_users(user_type);
CREATE INDEX idx_eo_users_is_active ON eo_users(is_active);
`;
