// Create user_stats table for caching user statistics locally
// This allows offline display of stats fetched from the API
export const createUserStatsMigration = `
CREATE TABLE IF NOT EXISTS user_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmers_reached_week INTEGER NOT NULL DEFAULT 0,
    farmers_reached_month INTEGER NOT NULL DEFAULT 0,
    farmers_reached_all INTEGER NOT NULL DEFAULT 0,
    conversations_resolved_week INTEGER NOT NULL DEFAULT 0,
    conversations_resolved_month INTEGER NOT NULL DEFAULT 0,
    conversations_resolved_all INTEGER NOT NULL DEFAULT 0,
    messages_sent_week INTEGER NOT NULL DEFAULT 0,
    messages_sent_month INTEGER NOT NULL DEFAULT 0,
    messages_sent_all INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
`;
