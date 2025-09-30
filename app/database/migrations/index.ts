// Migration exports for easy importing
export { eoUsersMigration } from './001_create_eo_users_table';
export { customerUsersMigration } from './002_create_customer_users_table';
export { messagesMigration } from './003_create_messages_table';
export { syncLogsMigration } from './004_create_sync_logs_table';

// Import the migrations for the array
import { eoUsersMigration } from './001_create_eo_users_table';
import { customerUsersMigration } from './002_create_customer_users_table';
import { messagesMigration } from './003_create_messages_table';
import { syncLogsMigration } from './004_create_sync_logs_table';

// Type definition for migration objects
export interface Migration {
  version: number;
  name: string;
  migration: string;
}

// Array of all migrations organized by version
export const allMigrations: Migration[] = [
  // Version 1 migrations - Initial database setup
  { version: 1, name: 'eo_users', migration: eoUsersMigration },
  { version: 1, name: 'customer_users', migration: customerUsersMigration },
  { version: 1, name: 'messages', migration: messagesMigration },
  { version: 1, name: 'sync_logs', migration: syncLogsMigration },
  
  // Future version 2 migrations can be added here
  // { version: 2, name: 'some_new_table', migration: someNewTableMigration },
];

// Helper function to get migrations by version
export const getMigrationsByVersion = (version: number): Migration[] => {
  return allMigrations.filter(migration => migration.version === version);
};
