// Profile table migration
export const profileMigration = `
-- Profile table migration
-- This table stores user profile data including access tokens and sync settings
CREATE TABLE profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userId INTEGER UNIQUE NOT NULL,
    accessToken TEXT UNIQUE NOT NULL,
    syncWifiOnly BOOLEAN NOT NULL DEFAULT 0,
    syncInterval INTEGER NOT NULL DEFAULT 15,
    language TEXT NOT NULL DEFAULT 'en',
    lastSyncAt TEXT NULL,
    createdAt TEXT NOT NULL DEFAULT (datetime('now')),
    updatedAt TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX idx_profile_userId ON profile(userId);
CREATE INDEX idx_profile_accessToken ON profile(accessToken);
`;
