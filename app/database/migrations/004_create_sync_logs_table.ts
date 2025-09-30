// Sync Logs table migration
export const syncLogsMigration = `
-- Sync Logs table migration
-- This table stores synchronization process logs
CREATE TABLE sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL, -- 'full', 'incremental', 'partial', etc.
    status INTEGER NOT NULL DEFAULT 0, -- 0: pending, 1: in progress, 2: completed, 3: failed
    started_at TEXT NOT NULL, -- ISO 8601 timestamp
    completed_at TEXT NULL, -- ISO 8601 timestamp
    details TEXT NULL, -- JSON details of the sync process
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Create indexes for better query performance
CREATE INDEX idx_sync_logs_sync_type ON sync_logs(sync_type);
CREATE INDEX idx_sync_logs_status ON sync_logs(status);
CREATE INDEX idx_sync_logs_started_at ON sync_logs(started_at);
CREATE INDEX idx_sync_logs_completed_at ON sync_logs(completed_at);
`;
